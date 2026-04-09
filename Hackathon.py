import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches

#Konstanten +++++++++++++++++++++++++++++++++++++++++++++++++++++++++
delta_t = 300 #sekunden
#Gebäude
R_building = 0.014
C_building = 5e7 
T_soll = 20
#Wärmepumpe
a = 3.5
b = -0.1
Q_wp_max = 10000.0
#Thermischer Speicher
E_th_max = 7000.0
Q_store_max = 10000.0
#Batteriespeicher
E_bat_max = 10000.0
P_bat_max = 5000.0
#PV-Anlage
PV_efficiency = 0.2
A_pv = 100

#Daten aus CSV auslesen ++++++++++++++++++++++++++++++++++++++++++++++
data = pd.read_csv("Daten_Hackathon.csv")       
n = len(data)       
timestamp = data.iloc[:, 0].to_numpy()          #Timestamp aus CSV                           
GHI = data.iloc[:, 1].to_numpy()                #GHI Strahlung für PV in W/m²          
T_out = data.iloc[:, 3].to_numpy()              #Aussentemperatur in °C           
Q_solarthermie = data.iloc[:, 4].to_numpy()     #Solarthermie-Erzeugung in W                   
Price = data.iloc[:, 5].to_numpy()              #Strompreis in €/kWh           
P_demand = data.iloc[:, 6].to_numpy()        #elektrischer Bedarf in W           
Q_demand = data.iloc[:, 7].to_numpy()        #aktueller thermischer Bedarf in W           

timestamp_dt = pd.to_datetime(timestamp, errors="coerce")

def simulate(price_low, price_high, return_series=False):
    #Berechnung
    T_in = np.zeros(n)
    T_in[0] = 20    #Startwert 20°C
    E_th = np.zeros(n + 1)
    E_th[0] = 3500                         #Startwert 3500 Wh
    E_bat = np.zeros(n + 1)
    E_bat[0] = 5000                        #Startwert 5000 Wh

    Q_wp = 0
    P_wp = 0
    Q_heat = 0
    Q_store = 0
    P_pv = 0
    P_bat = 0
    delta_T_in = 0

    P_buy = 0
    Cost = 0

    P_sum_load = 0
    P_sum_buy = 0
    E_pv = 0
    E_sum_pv = 0
    cost_steps = np.zeros(n)

    q_wp_series = np.zeros(n)
    p_wp_series = np.zeros(n)
    p_pv_series = np.zeros(n)
    p_bat_series = np.zeros(n)
    p_grid_buy_series = np.zeros(n)
    p_grid_sell_series = np.zeros(n)

    kp = 0.1
    e_temp = 0
    u_temp = 0

    f_wp = np.zeros(4)            #Faktor, wieviel % von der benötigten Wärmeleistung die WP laufen soll --> rest aus speicher
    f_store_th = np.zeros(4)      #Faktor, wieviel % von der max. leistung in den Speicher die WP zusätzlich läuft, um Speicher zu füllen

    f_bat_use = np.zeros(6)        #Faktor, wieviel % von der benötigten el-Leistung aus der Batterie gezogen wird.
    f_bat_sell = np.zeros(6)       #Faktor, wieviel % von der max.Leistung der Batterie zusätlich die Betterie geladen/entladen werden soll.

    for i in range(n):

        #Berechnung Außeneinflüsse
        P_pv = GHI[i] * A_pv * PV_efficiency
        E_pv = (P_pv / 1000) * (delta_t / 3600)
        E_sum_pv += E_pv
        COP = a - b * T_out[i]

        #Berechnung Speicherstand in Prozent
        E_bat_pct = E_bat[i] / E_bat_max
        E_th_pct = E_th[i] / E_th_max

        #Temp. regelung mit P-Regler
        e_temp = T_soll - T_in[i]
        u_temp = kp * e_temp
        if u_temp < 0:
            u_temp = 0
        Q_heat = u_temp * Q_store_max

        #Berrechnung benötigte Wärmeleistung --> die Heizleistung - Leistung der Solarthermie
        Q_needed = Q_heat - Q_solarthermie[i]

        # Einstellung der Faktoren für Wärmepumpe, Speicher und Batterie, je nach Strompreis
        match Price[i]:
            case x if x < 0:
                f_wp[0] = 1
                f_wp[1] = 1
                f_wp[2] = 1
                f_wp[3] = 1

                f_store_th[0] = 0
                f_store_th[1] = 1
                f_store_th[2] = 1
                f_store_th[3] = 1

                f_bat_use[0] = 0
                f_bat_use[1] = 0
                f_bat_use[2] = 0
                f_bat_use[3] = 0
                f_bat_use[4] = 0
                f_bat_use[5] = 0

                f_bat_sell[0] = 0
                f_bat_sell[1] = -0.1
                f_bat_sell[2] = -0.5
                f_bat_sell[3] = -1
                f_bat_sell[4] = -1
                f_bat_sell[5] = -1
            case x if x < price_low and x >= 0:
                f_wp[0] = 0.5
                f_wp[1] = 0.75
                f_wp[2] = 1
                f_wp[3] = 1

                f_store_th[0] = 0
                f_store_th[1] = 0.05
                f_store_th[2] = 0.1
                f_store_th[3] = 0.2

                f_bat_use[0] = 1
                f_bat_use[1] = 1
                f_bat_use[2] = 0.5
                f_bat_use[3] = 0
                f_bat_use[4] = 0
                f_bat_use[5] = 0

                f_bat_sell[0] = 0
                f_bat_sell[1] = 0
                f_bat_sell[2] = 0
                f_bat_sell[3] = 0
                f_bat_sell[4] = -0.1
                f_bat_sell[5] = -0.2
            case x if x < price_high and x >= price_low:
                f_wp[0] = 0.25
                f_wp[1] = 0.5
                f_wp[2] = 0.75
                f_wp[3] = 1

                f_store_th[0] = 0
                f_store_th[1] = 0
                f_store_th[2] = 0
                f_store_th[3] = 0.1

                f_bat_use[0] = 1
                f_bat_use[1] = 1
                f_bat_use[2] = 0.75
                f_bat_use[3] = 0.5
                f_bat_use[4] = 0.25
                f_bat_use[5] = 0

                f_bat_sell[0] = 0
                f_bat_sell[1] = 0
                f_bat_sell[2] = 0
                f_bat_sell[3] = 0
                f_bat_sell[4] = 0
                f_bat_sell[5] = 0
            case x if x >= price_high:
                f_wp[0] = 0
                f_wp[1] = 0.25
                f_wp[2] = 0.5
                f_wp[3] = 0.75

                f_store_th[0] = 0
                f_store_th[1] = 0
                f_store_th[2] = 0
                f_store_th[3] = 0

                f_bat_use[0] = 1
                f_bat_use[1] = 1
                f_bat_use[2] = 1
                f_bat_use[3] = 0.75
                f_bat_use[4] = 0.5
                f_bat_use[5] = 0.25

                f_bat_sell[0] = 0
                f_bat_sell[1] = 0
                f_bat_sell[2] = 0
                f_bat_sell[3] = 0
                f_bat_sell[4] = 0
                f_bat_sell[5] = 0

        # Einstellung der Wärmepumpe und des Bezugs aus dem thermischen Speicher mit den eingestellten Faktoren (je nach Speicherstand)
        if Q_needed > 0:
            match E_th_pct:
                case x if x > 0.8:
                    Q_wp = min((f_wp[0] * Q_needed + f_store_th[0] * Q_store_max), Q_wp_max)
                    Q_store = Q_needed - Q_wp
                case x if x > 0.5:
                    Q_wp = min((f_wp[1] * Q_needed + f_store_th[1] * Q_store_max), Q_wp_max)
                    Q_store = Q_needed - Q_wp
                case x if x > 0.2:
                    Q_wp = min((f_wp[2] * Q_needed + f_store_th[2] * Q_store_max), Q_wp_max)
                    Q_store = Q_needed - Q_wp
                case x if x > 0.005:
                    Q_wp = min((f_wp[3] * Q_needed + f_store_th[3] * Q_store_max), Q_wp_max)
                    Q_store = Q_needed - Q_wp
                case _:
                    Q_wp = Q_needed
                    Q_store = 0
        else:
            if E_th_pct < 1:
                if E_th_pct < 0.8:
                    Q_wp = 0.1 * Q_store_max
                else:
                    Q_wp = 0
                Q_store = Q_needed - Q_wp
            else:
                Q_wp = 0
                Q_store = 0
            # Was passiert, wenn Speicher voll und überschüssige Wärme????????

        #Berechnung des neuen thermischen Speicherstandes
        E_th[i + 1] = np.clip(E_th[i] - (Q_store * (delta_t / 3600)), 0, E_th_max)
        #Berechnung der el. Leistung der Wärmepumpe
        P_wp = Q_wp / COP
        #Berechnung benötigte el.Leistung --> Leistung Wärmepumpe - PV Leistung
        P_needed = P_demand[i] + P_wp - P_pv

        # Einstellung des Bezugs aus der Batterie (laden oder entladen) und ob Strom gekauft oder verkauft wird (negativ = verkaufen)
        if P_needed > 0:
            match E_bat_pct:
                case x if x > 0.999:
                    P_bat = min((f_bat_use[0] * P_needed + f_bat_sell[0] * P_bat_max), P_bat_max)
                    P_buy = P_needed - P_bat

                case x if x > 0.9:
                    P_bat = min((f_bat_use[1] * P_needed + f_bat_sell[1] * P_bat_max), P_bat_max)
                    P_buy = P_needed - P_bat

                case x if x > 0.6:
                    P_bat = min((f_bat_use[2] * P_needed + f_bat_sell[2] * P_bat_max), P_bat_max)
                    P_buy = P_needed - P_bat

                case x if x > 0.3:
                    P_bat = min((f_bat_use[3] * P_needed + f_bat_sell[3] * P_bat_max), P_bat_max)
                    P_buy = P_needed - P_bat

                case x if x > 0.1:
                    P_bat = min((f_bat_use[4] * P_needed + f_bat_sell[4] * P_bat_max), P_bat_max)
                    P_buy = P_needed - P_bat

                case x if x > 0.005:
                    P_bat = min((f_bat_use[5] * P_needed + f_bat_sell[5] * P_bat_max), P_bat_max)
                    P_buy = P_needed - P_bat

                case _:
                    P_bat = 0
                    P_buy = P_needed

        else:
            surplus = -P_needed   # positiv

            # max. Ladeleistung der Batterie
            P_charge_max = min(P_bat_max, (E_bat_max - E_bat[i]) * 3600 / delta_t)

            # einfache preisbasierte Entscheidung
            if Price[i] < 0:
                f_charge = 1.0      # alles laden
            elif Price[i] < price_low:
                f_charge = 1.0      # eher speichern
            elif Price[i] < price_high:
                f_charge = 0.5      # halb speichern, halb verkaufen
            else:
                f_charge = 0.0      # lieber direkt verkaufen

            P_charge = min(f_charge * surplus, P_charge_max)

            P_bat = -P_charge           # negativ = Batterie laden
            P_buy = P_needed - P_bat    # negativ = Einspeisung/Verkauf
            # Was passiert, wenn Speicher voll und überschüssige Strom????????

        #Berrechnung des neuen Batteriestandes
        E_bat[i + 1] = np.clip(E_bat[i] - (P_bat * (delta_t / 3600)), 0, E_bat_max)

        #InnenTemp. berechnen
        if i < (n - 1):
            delta_T_in = (((T_out[i] - T_in[i]) / R_building) + Q_heat) * (delta_t / C_building)
            T_in[i + 1] = T_in[i] + delta_T_in

        #Kosten aufsummieren --> negativ=gewinn
        step_cost = (P_buy / 1000) * (delta_t / 3600) * Price[i]
        Cost += step_cost
        cost_steps[i] = step_cost

        q_wp_series[i] = Q_wp
        p_wp_series[i] = P_wp
        p_pv_series[i] = P_pv
        p_bat_series[i] = P_bat
        p_grid_buy_series[i] = max(P_buy, 0)
        p_grid_sell_series[i] = max(-P_buy, 0)

        P_sum_load += P_demand[i] + P_wp
        if P_buy > 0:
            P_sum_buy += P_buy

    autarkie = ((P_sum_load - P_sum_buy) / P_sum_load) * 100
    gewinn = -Cost

    if return_series:
        cum_gewinn = -np.cumsum(cost_steps)
        details = {
            "T_in": T_in.copy(),
            "T_out": T_out.copy(),
            "E_th": E_th[:-1].copy(),
            "E_bat": E_bat[:-1].copy(),
            "Q_wp": q_wp_series,
            "P_wp": p_wp_series,
            "P_pv": p_pv_series,
            "P_bat": p_bat_series,
            "P_grid_buy": p_grid_buy_series,
            "P_grid_sell": p_grid_sell_series,
            "P_demand": P_demand.copy(),
            "Price": Price.copy(),
        }
        return autarkie, gewinn, E_sum_pv, cum_gewinn, details

    return autarkie, gewinn, E_sum_pv


# Parametersuche
price_low_values = np.arange(-0.1, 0.1, 0.005)
price_high_values = np.arange(-0.1, 0.1, 0.005)

max_autarkie = -np.inf
best_low_autarkie = None
best_high_autarkie = None

max_gewinn = -np.inf
best_low_gewinn = None
best_high_gewinn = None

results = []

total_tests = sum(1 for pl in price_low_values for ph in price_high_values if ph > pl)
processed_tests = 0

def print_progress_bar(current, total, prefix="Fortschritt Parametersuche", length=30):
    percent = (current / total) if total else 1.0
    filled = int(length * percent)
    bar = "█" * filled + "░" * (length - filled)
    end_char = "\n" if current == total else "\r"
    print(f"{prefix}: |{bar}| {current}/{total} ({percent * 100:5.1f}%)", end=end_char, flush=True)

for price_low in price_low_values:
    for price_high in price_high_values:
        # Nur sinnvolle Kombinationen testen
        if price_high <= price_low:
            continue

        processed_tests += 1

        autarkie, gewinn, _ = simulate(price_low, price_high)
        results.append((price_low, price_high, autarkie, gewinn))

        # Live-Fortschrittsanzeige als einzeiliger Balken
        print_progress_bar(processed_tests, total_tests)

        if autarkie > max_autarkie:
            max_autarkie = autarkie
            best_low_autarkie = price_low
            best_high_autarkie = price_high

        if gewinn > max_gewinn:
            max_gewinn = gewinn
            best_low_gewinn = price_low
            best_high_gewinn = price_high

# Sweet Spot: gewichteter Kompromiss aus normierter Autarkie und normiertem Gewinn
weight_autarkie = 0.1
weight_gewinn = 0.9

autarkie_vals = [r[2] for r in results]
gewinn_vals = [r[3] for r in results]

aut_min = min(autarkie_vals)
aut_max = max(autarkie_vals)
gew_min = min(gewinn_vals)
gew_max = max(gewinn_vals)

best_score = -np.inf
sweet_low = None
sweet_high = None
sweet_autarkie = None
sweet_gewinn = None

for pl, ph, aut, gew in results:

    if aut_max > aut_min:
        aut_norm = (aut - aut_min) / (aut_max - aut_min)
    else:
        aut_norm = 1.0

    if gew_max > gew_min:
        gew_norm = (gew - gew_min) / (gew_max - gew_min)
    else:
        gew_norm = 1.0

    score = weight_autarkie * aut_norm + weight_gewinn * gew_norm

    if score > best_score:
        best_score = score
        sweet_low = pl
        sweet_high = ph
        sweet_autarkie = aut
        sweet_gewinn = gew

print(f"MAX(Autarkie): {max_autarkie:10.3f} % bei price_low={best_low_autarkie:.3f}, price_high={best_high_autarkie:.3f}")
print(f"MAX(Gewinn):   {max_gewinn:10.3f} € bei price_low={best_low_gewinn:.3f}, price_high={best_high_gewinn:.3f}")
print(
    f"Sweet Spot:    score={best_score:6.3f}, Autarkie={sweet_autarkie:10.3f} %, "
    f"Gewinn={sweet_gewinn:10.3f} € bei price_low={sweet_low:.3f}, price_high={sweet_high:.3f}"
)

# Separater Plot: Gewinn über min/max-Zonen mit markiertem Hochpunkt
zones_df = pd.DataFrame(results, columns=["price_low", "price_high", "autarkie", "gewinn"])
gewinn_grid = zones_df.pivot(index="price_high", columns="price_low", values="gewinn")

fig_zone, ax_zone = plt.subplots(figsize=(9, 7))
zone_cmap = plt.get_cmap("viridis").copy()
zone_cmap.set_bad(color="#d9d9d9")
masked_gewinn = np.ma.masked_invalid(gewinn_grid.to_numpy())

mesh = ax_zone.pcolormesh(
    gewinn_grid.columns.to_numpy(),
    gewinn_grid.index.to_numpy(),
    masked_gewinn,
    shading="auto",
    cmap=zone_cmap,
)
cbar = plt.colorbar(mesh, ax=ax_zone)
cbar.set_label("Gewinn [€]")

# Trennlinie zwischen gültigem (price_high > price_low) und ungültigem Bereich
diag_x = np.array([price_low_values.min(), price_low_values.max()])
ax_zone.plot(diag_x, diag_x, color="white", linestyle="--", linewidth=1.2, label="Grenze: price_high = price_low")

# Ungültigen Bereich zusätzlich schraffieren (max <= min)
ax_zone.fill_between(
    diag_x,
    price_low_values.min(),
    diag_x,
    color="none",
    hatch="///",
    edgecolor="#808080",
    linewidth=0.0,
)

ax_zone.scatter(
    best_low_gewinn,
    best_high_gewinn,
    color="red",
    edgecolor="white",
    linewidth=0.8,
    s=90,
    zorder=5,
    label="Hochpunkt (MAX Gewinn)",
)
ax_zone.annotate(
    f"MAX: {max_gewinn:.2f} €\nlow={best_low_gewinn:.3f}, high={best_high_gewinn:.3f}",
    xy=(best_low_gewinn, best_high_gewinn),
    xytext=(15, 10),
    textcoords="offset points",
    fontsize=9,
    bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.85),
)

ax_zone.set_title("Gewinn über Min/Max-Zonen (price_low vs. price_high)")
ax_zone.set_xlabel("price_low [€/kWh]")
ax_zone.set_ylabel("price_high [€/kWh]")
invalid_patch = mpatches.Patch(facecolor="#d9d9d9", edgecolor="#808080", hatch="///", label="Ungültig: price_high <= price_low")
handles, labels = ax_zone.get_legend_handles_labels()
handles.append(invalid_patch)
labels.append("Ungültig: price_high <= price_low")
ax_zone.legend(handles, labels, loc="best")
ax_zone.grid(alpha=0.25)

fig_zone.tight_layout()
fig_zone.savefig("gewinn_minmax_zonen_hochpunkt.png", dpi=150, bbox_inches="tight")

# Daten für den Gesamtplot (inkl. kumulierter Gewinn)
_, sweet_gewinn_check, _, sweet_cum_gewinn, sweet_details = simulate(
    sweet_low, sweet_high, return_series=True
)

# Erweiterte Grafische Ausgabe: alle wichtigen Eigenschaften für den Sweet Spot
fig_all, axes = plt.subplots(6, 1, figsize=(14, 18), sharex=True)

if timestamp_dt.notna().any():
    x_all = timestamp_dt
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
    fig_all.autofmt_xdate()
else:
    x_all = np.arange(n) * (delta_t / 3600)
    axes[-1].set_xlabel("Zeit [h]")

if timestamp_dt.notna().any():
    axes[0].set_xlabel("Zeit")

axes[0].plot(x_all, sweet_cum_gewinn, color="tab:green", linewidth=1.4, label="Kumulierter Gewinn")
axes[0].axhline(0, color="black", linestyle="--", linewidth=0.8)
axes[0].set_ylabel("€")
axes[0].set_title("Einnahmen/Gewinn über Zeit")
axes[0].grid(alpha=0.3)
axes[0].legend(loc="best")

axes[1].plot(x_all, sweet_details["Price"], color="tab:blue", linewidth=1.0, label="Strompreis")
axes[1].axhline(sweet_low, color="tab:orange", linestyle="--", linewidth=0.9, label=f"price_low={sweet_low:.3f}")
axes[1].axhline(sweet_high, color="tab:red", linestyle="--", linewidth=0.9, label=f"price_high={sweet_high:.3f}")
axes[1].set_ylabel("€/kWh")
axes[1].set_title("Preisverlauf mit Sweet-Spot-Grenzen")
axes[1].grid(alpha=0.3)
axes[1].legend(loc="best")

axes[2].plot(x_all, sweet_details["T_in"], color="tab:red", linewidth=1.0, label="Innen")
axes[2].plot(x_all, sweet_details["T_out"], color="tab:cyan", linewidth=0.9, label="Außen")
axes[2].axhline(T_soll, color="gray", linestyle=":", linewidth=0.9, label="T_soll")
axes[2].set_ylabel("°C")
axes[2].set_title("Temperaturen")
axes[2].grid(alpha=0.3)
axes[2].legend(loc="best")

axes[3].plot(x_all, sweet_details["E_th"], color="tab:orange", linewidth=1.0, label="Thermischer Speicher")
axes[3].plot(x_all, sweet_details["E_bat"], color="tab:purple", linewidth=1.0, label="Batterie")
axes[3].set_ylabel("Wh")
axes[3].set_title("Speicherstände")
axes[3].grid(alpha=0.3)
axes[3].legend(loc="best")

axes[4].plot(x_all, sweet_details["P_pv"], color="goldenrod", linewidth=1.0, label="PV")
axes[4].plot(x_all, sweet_details["P_wp"], color="tab:blue", linewidth=1.0, label="WP el.")
axes[4].plot(x_all, sweet_details["P_demand"], color="tab:gray", linewidth=0.9, label="Haushalt")
axes[4].plot(x_all, sweet_details["P_bat"], color="tab:purple", linewidth=0.9, label="Batterie (+entladen / -laden)")
axes[4].set_ylabel("W")
axes[4].set_title("Leistungen")
axes[4].grid(alpha=0.3)
axes[4].legend(loc="best")

axes[5].fill_between(
    x_all,
    0,
    sweet_details["P_grid_buy"],
    color="tab:red",
    alpha=0.55,
    label="Netzbezug",
)
axes[5].fill_between(
    x_all,
    0,
    sweet_details["P_grid_sell"],
    color="tab:green",
    alpha=0.55,
    label="Einspeisung",
)
axes[5].set_ylabel("W")
axes[5].set_title("Netzbezug und Einspeisung")
axes[5].grid(alpha=0.3)
axes[5].legend(loc="best")

fig_all.suptitle(
    "Sweet Spot - Wichtige Eigenschaften über Zeit\n"
    f"price_low={sweet_low:.3f}, price_high={sweet_high:.3f}, "
    f"Gewinn={sweet_gewinn_check:.2f} €, Autarkie={sweet_autarkie:.2f} %",
    fontsize=12,
)

fig_all.tight_layout(rect=[0, 0, 1, 0.97])
fig_all.savefig("sweet_spot_alle_eigenschaften.png", dpi=150, bbox_inches="tight")

# Nur ein show-Aufruf: beide Figuren erscheinen gleichzeitig.
plt.show()
