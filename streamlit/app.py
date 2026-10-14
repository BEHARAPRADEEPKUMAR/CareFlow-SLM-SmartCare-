import requests
import streamlit as st

st.set_page_config(page_title="CareFlow-SLM", page_icon="✦", layout="wide")
st.markdown("""
<style>
.stApp { background:#F4F8FA; }
h1,h2,h3 { color:#123B63; }
</style>
""", unsafe_allow_html=True)

st.title("CareFlow-SLM")
st.caption("Vertical AI Healthcare Appointment & Patient Communication")
api = st.sidebar.text_input("Django API", "http://127.0.0.1:8000/api")

a,b,c,d = st.columns(4)
a.metric("SLM","Adapter Ready")
b.metric("RAG","Enabled")
c.metric("Safety","Enabled")
d.metric("Workflow","Ready")

st.subheader("AI Testing Console")
msg = st.text_area("Patient message","I want to book a cardiology appointment tomorrow at 15:00")
if st.button("Run CareFlow AI", type="primary"):
    try:
        r = requests.post(f"{api}/chat/", json={"message":msg}, timeout=10)
        if r.ok:
            x=r.json()
            st.write("**Intent:**", x["intent"])
            st.write("**Entities:**", x["entities"])
            st.write("**Safety:**", x["safety"]["level"])
            st.success(x["response"])
            st.json(x)
        else:
            st.error(r.text)
    except requests.RequestException as e:
        st.error(f"Backend unavailable: {e}")

st.divider()
st.code("Patient → Safety → SLM → RAG/Database → Workflow → Response")
