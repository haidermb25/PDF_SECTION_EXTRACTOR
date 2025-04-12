import streamlit as st
import psycopg2
from psycopg2 import sql
from groq import Groq
import os
# Initialize Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
# Brand lists
neumann_brands = ["Acrison", "Air+", "Alfa Laval", "Afton Pump", "Aqueous Vets", "Big Wave", "Börger", "CB&I", "Charter Machine", "Clearstream", "Cleveland Mixer", "Creston", "Custom Conveyor", "Dakota Pump", "Daniel Mechanical", "Dupont/Memcor", "Ecoremedy", "Environmental Dynamics", "Environetics", "Esmil", "Evoqua", "Flonergia", "Gardner Denver", "Hoffman & Lamson", "Hallsten", "Hellan Strainer", "Hendrick Screen", "Inovair", "Komline", "Krofta", "Kurita", "Tonka", "Lakeside Equipment", "Lovibond", "Macrotech", "Mass Transfer Systems", "Merit Filter", "Merrick Industries", "Moleaer", "Napier-Reid", "Nefco", "Nexom", "Nordic Water", "Nuove Energie", "Powell", "Primozone", "Purafil", "Rebuild-It", "Reid Lifting", "Robuschi", "Roto Pumps", "RSA Protect", "S & N Airoflo", "Schwing Bioset", "Sentry", "SFA-Enviro", "Smith & Loveless", "Trojan", "Unifilt", "Vaughan", "Wastecorp", "Waterman", "Waterman Industries", "Westfall", "Wigen", "Wilo"]

macaulay_brands = ["Ashcroft", "Assmann", "Blue-White", "Cattron", "Cla-Val Company", "Constant Chlor Plus", "Emerson", "Entech Design", "Flow-Tronic", "ProMinent Fluid Controls", "The Mastrrr Company", "Primary Fluid Systems", "Sage Metering", "Regal", "RKI Instruments", "Scaletron", "Wey Valve", "Sensidyne"]

# Database connection
def get_db_connection():
    return psycopg2.connect(
        "postgresql://neondb_owner:npg_noGpAjWE04ym@ep-fragrant-forest-a5ikkddc-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    )

def get_all_section_names():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT section_name FROM pdf ORDER BY section_name")
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def get_section_content(section_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT content FROM pdf WHERE section_name = %s", (section_name,))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        cursor.close()
        conn.close()

def get_manufacturers_info(content):
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """Extract and list all manufacturer names mentioned in this construction specification. 
                Return the manufacturers in a clean list format. If no manufacturers are found, 
                simply state 'No manufacturers found'."""
            },
            {
                "role": "user",
                "content": f"CONSTRUCTION SPECIFICATION CONTENT:\n{content}"
            }
        ],
        temperature=0.1,
        max_tokens=500
    )
    return response.choices[0].message.content

def main():
    st.markdown("""
        <style>
        #MainMenu, header, footer {
            visibility: hidden;
        }
        </style>
      """, unsafe_allow_html=True)
    st.title("🔧 Construction Specifications Analyzer")
    st.markdown("### Extract manufacturer information from specification sections")

    sections = get_all_section_names()
    if not sections:
        st.warning("No sections found in database!")
        return

    selected_section = st.selectbox("Select a section:", sections)

    if st.button("Get Manufacturer Information"):
        with st.spinner(f"Analyzing {selected_section}..."):
            content = get_section_content(selected_section)
            if not content:
                st.error("Section content not found")
                return

            manufacturer_info = get_manufacturers_info(content)

            st.subheader(f"Manufacturer Information in {selected_section}")
            st.markdown(manufacturer_info)

            # Parse manufacturer list from output
            manufacturers = [
                m.strip("-• \n") for m in manufacturer_info.splitlines()
                if m.strip() and not m.lower().startswith("no manufacturer")
            ]

            matched_neumann = []
            matched_macaulay = []
            unmatched = []

            for m in manufacturers:
                if m in neumann_brands:
                    matched_neumann.append(m)
                elif m in macaulay_brands:
                    matched_macaulay.append(m)
                else:
                    unmatched.append(m)

            st.markdown("#### ✅ Match Summary:")
            if matched_neumann:
                st.success(f"**Neumann Brands:** {', '.join(matched_neumann)}")
            if matched_macaulay:
                st.success(f"**Macaulay Brands:** {', '.join(matched_macaulay)}")
            if unmatched:
                st.warning(f"**Not Found in Brand Lists:** {', '.join(unmatched)}")

            with st.expander("📄 View Section Content"):
                st.code(content[:10000] + ("..." if len(content) > 10000 else ""), language='text')

if __name__ == "__main__":
    main()
