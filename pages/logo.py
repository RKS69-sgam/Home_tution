
# Header logo
st.sidebar.title("Login / New Registration")
prk_logo_b64 = get_image_as_base64("PRK_logo.jpg")
excellent_logo_b64 = get_image_as_base64("Excellent_logo.jpg")
if prk_logo_b64 and excellent_logo_b64:
    st.markdown(f"""<div style="text-align: center;"><h2>Excellent Public School High-tech Homework System 📈</h2></div>""", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1: st.image("PRK_logo.jpg")
    with col2: st.image("Excellent_logo.jpg")
st.markdown("---")
