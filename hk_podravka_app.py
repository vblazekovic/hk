"""
HK Podravka – Streamlit aplikacija (patchirana verzija)
------------------------------------------------------
Ova verzija uključuje ispravan import Streamlita i robusnu funkciju za odabir trenera.
Ako već imaš kompletnu aplikaciju, najlakše je:
1) Prebaciti funkciju `select_coach` u tvoj file,
2) Zamijeniti postojeći `st.selectbox(...)` s primjerom ispod (ili pozvati `select_coach`),
3) Obrisati demo blok na dnu.

Ako želiš odmah pokrenuti i testirati, pokreni:
    streamlit run hk_podravka_app.py
"""

import streamlit as st
import pandas as pd


def select_coach(coaches: pd.DataFrame, label: str = "Trener"):
    """
    Rendera selectbox s trenerima iz DataFramea `coaches` (stupci: 'id', 'name').
    Vraća odabrani `id` (kao string) ili None ako je odabran "-".
    """
    if coaches is None or coaches.empty:
        st.warning("Lista trenera je prazna.")
        st.selectbox(label, ["-"], index=0)
        return None

    # Ispravno formiranje opcija bez escape znakova u f-stringu
    options = ["-"] + [f"{r['id']} – {r['name']}" for _, r in coaches.iterrows()]
    choice = st.selectbox(label, options, index=0)

    if choice == "-":
        return None

    # Parsiranje ID-a iz prikaza "ID – Ime"
    if "–" in choice:
        coach_id = choice.split("–", 1)[0].strip()
    else:
        coach_id = choice.split("-", 1)[0].strip()
    return coach_id


def main():
    st.set_page_config(page_title="HK Podravka", layout="wide")
    st.title("HK Podravka – Admin")
    st.caption("Patchirana verzija selectbox-a za odabir trenera")

    # --- OVDJE UBACI TVOJE POSTOJEĆE UČITAVANJE PODATAKA ---
    # Primjer demo DataFramea (zamijeni svojim podacima):
    coaches = pd.DataFrame([
        {"id": 1, "name": "Ana K."},
        {"id": 2, "name": "Marko P."},
        {"id": 3, "name": "Iva S."},
    ])

    st.subheader("Odabir trenera (sigurna sintaksa)")

    # VARIJANTA A: direktno u liniji (ako želiš zadržati stari stil)
    c_display = st.selectbox(
        "Trener (direktno)",
        ["-"] + [f"{r['id']} – {r['name']}" for _, r in coaches.iterrows()],
        index=0,
        key="coach_direct",
    )
    selected_id_a = None if c_display == "-" else c_display.split("–", 1)[0].split("-", 1)[0].strip()
    st.write("Odabrani ID (direktno):", selected_id_a)

    # VARIJANTA B: preko helper funkcije
    selected_id_b = select_coach(coaches, label="Trener (helper)")
    st.write("Odabrani ID (helper):", selected_id_b)

    st.info("U tvom originalnom fileu zamijeni problematičnu liniju ovim obrascem ili koristi funkciju select_coach.")


if __name__ == "__main__":
    main()
