# Ispravljena verzija dijela hk_podravka_app.py

c_id = st.selectbox(
    "Trener",
    ["-"] + [f"{r['id']} – {r['name']}" for _, r in coaches.iterrows()]
)

# Ako u drugim dijelovima koda imaš slične izraze, pravilno ih piši ovako:
# f"{r['id']} - {r['name']}"
# f'{r["id"]} - {r["name"]}'
