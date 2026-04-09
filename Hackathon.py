import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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

        P_sum_load += P_demand[i] + P_wp
        if P_buy > 0:
            P_sum_buy += P_buy

    autarkie = ((P_sum_load - P_sum_buy) / P_sum_load) * 100
    gewinn = -Cost

    if return_series:
        cum_gewinn = -np.cumsum(cost_steps)
        return autarkie, gewinn, E_sum_pv, cum_gewinn

    return autarkie, gewinn, E_sum_pv


# Parametersuche
price_low_values = np.arange(0.01, 0.1, 0.005)
price_high_values = np.arange(0.01, 0.1, 0.005)

max_autarkie = -np.inf
best_low_autarkie = None
best_high_autarkie = None

max_gewinn = -np.inf
best_low_gewinn = None
best_high_gewinn = None

results = []

total_tests = sum(1 for pl in price_low_values for ph in price_high_values if ph > pl)
processed_tests = 0

for price_low in price_low_values:
    for price_high in price_high_values:
        # Nur sinnvolle Kombinationen testen
        if price_high <= price_low:
            continue

        processed_tests += 1

        autarkie, gewinn, _ = simulate(price_low, price_high)
        results.append((price_low, price_high, autarkie, gewinn))

        # Live-Fortschrittsanzeige waehrend der Parametersuche
        if processed_tests == 1 or processed_tests % 1 == 0 or processed_tests == total_tests:
            progress_pct = (processed_tests / total_tests) * 100
            print(
                f"Fortschritt Parametersuche: {processed_tests}/{total_tests} ({progress_pct:5.1f}%)",
                flush=True,
            )

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

# Grafische Ausgabe: kumulierter Gewinn über Zeit für den Sweet Spot
_, sweet_gewinn_check, _, sweet_cum_gewinn = simulate(sweet_low, sweet_high, return_series=True)

fig, ax = plt.subplots(figsize=(12, 5))

if timestamp_dt.notna().any():
    x_values = timestamp_dt
    ax.plot(x_values, sweet_cum_gewinn, color="tab:green", linewidth=1.5, label="Kumulierter Gewinn")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
    fig.autofmt_xdate()
    ax.set_xlabel("Zeit")
else:
    x_values = np.arange(n) * (delta_t / 3600)
    ax.plot(x_values, sweet_cum_gewinn, color="tab:green", linewidth=1.5, label="Kumulierter Gewinn")
    ax.set_xlabel("Zeit [h]")

ax.axhline(0, color="black", linestyle="--", linewidth=0.8)
ax.set_ylabel("Einnahmen / Gewinn [€]")
ax.set_title(
    "Einnahmen über Zeit (Sweet Spot)\n"
    f"price_low={sweet_low:.3f}, price_high={sweet_high:.3f}, Gewinn Ende={sweet_gewinn_check:.2f} €"
)
ax.grid(alpha=0.3)
ax.legend(loc="best")

plt.tight_layout()
plt.savefig("sweet_spot_einnahmen_zeit.png", dpi=150, bbox_inches="tight")
plt.show()
