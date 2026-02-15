import streamlit as st
import requests

st.set_page_config(page_title="English to Tamil Translator")

st.title("English ➜ Tamil Translator")
st.write("Streamlit + Flask API POC")

english_text = st.text_area("Enter English Text")

if st.button("Translate"):
    if english_text.strip():
        response = requests.post(
            "http://127.0.0.1:5000/translate",
            json={"text": english_text}
        )

        if response.status_code == 200:
            tamil = response.json()["tamil"]
            st.success("Tamil Translation")
            st.write(tamil)
        else:
            st.error("Translation failed")
    else:
        st.warning("Please enter text")
