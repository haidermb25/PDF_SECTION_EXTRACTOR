import streamlit as st
import psycopg2
from groq import Groq
import concurrent.futures
import textwrap
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Manufacturer brand lists (fill these with your actual brand lists)
neumann_brands = ["Acrison", "Air+", "Alfa Laval", "Afton Pump", "Aqueous Vets", "Big Wave", "Börger", "CB&I", "Charter Machine", "Clearstream", "Cleveland Mixer", "Creston", "Custom Conveyor", "Dakota Pump", "Daniel Mechanical", "Dupont/Memcor", "Ecoremedy", "Environmental Dynamics", "Environetics", "Esmil", "Evoqua", "Flonergia", "Gardner Denver", "Hoffman & Lamson", "Hallsten", "Hellan Strainer", "Hendrick Screen", "Inovair", "Komline", "Krofta", "Kurita", "Tonka", "Lakeside Equipment", "Lovibond", "Macrotech", "Mass Transfer Systems", "Merit Filter", "Merrick Industries", "Moleaer", "Napier-Reid", "Nefco", "Nexom", "Nordic Water", "Nuove Energie", "Powell", "Primozone", "Purafil", "Rebuild-It", "Reid Lifting", "Robuschi", "Roto Pumps", "RSA Protect", "S & N Airoflo", "Schwing Bioset", "Sentry", "SFA-Enviro", "Smith & Loveless", "Trojan", "Unifilt", "Vaughan", "Wastecorp", "Waterman", "Waterman Industries", "Westfall", "Wigen", "Wilo"]

macaulay_brands = ["BrandA", "BrandB"]

# Database connection
def get_db_connection():
    return psycopg2.connect(
        "postgresql://neondb_owner:npg_noGpAjWE04ym@ep-fragrant-forest-a5ikkddc-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    )

@st.cache_data
def get_unique_pdf_names():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT pdf_name FROM pdf ORDER BY pdf_name")
            return [row[0] for row in cursor.fetchall()]

@st.cache_data
def get_sections_for_pdf(pdf_name):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT section_name FROM pdf WHERE pdf_name = %s ORDER BY section_name", (pdf_name,))
            return [row[0] for row in cursor.fetchall()]

@st.cache_data
def get_section_content(pdf_name, section_name):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT content FROM pdf WHERE pdf_name = %s AND section_name = %s", 
                         (pdf_name, section_name))
            result = cursor.fetchone()
            return result[0] if result else None

# Split large content for concurrent API calls
def split_content_for_api(content, chunk_token_limit=3000):
    char_limit = chunk_token_limit * 4
    return textwrap.wrap(content, char_limit, break_long_words=False, replace_whitespace=False)

def extract_manufacturers_chunk(chunk):
    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {
                    "role": "system",
                    "content": """Extract and list all manufacturer names mentioned in this construction specification. 
                    Return the manufacturers in a clean list format. If no manufacturers are found, 
                    simply state 'No manufacturers found'."""
                },
                {
                    "role": "user",
                    "content": f"CONSTRUCTION SPECIFICATION CONTENT:\n{chunk}"
                }
            ],
            temperature=0.1,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error extracting manufacturers: {str(e)}"

def get_manufacturers_info(content):
    chunks = split_content_for_api(content)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(extract_manufacturers_chunk, chunks))
    return "\n".join(results)

def match_brands(manufacturer_list):
    matched_neumann, matched_macaulay, unmatched = [], [], []
    for m in manufacturer_list:
        clean = m.strip("-• \n")
        if clean in neumann_brands:
            matched_neumann.append(clean)
        elif clean in macaulay_brands:
            matched_macaulay.append(clean)
        else:
            unmatched.append(clean)
    return matched_neumann, matched_macaulay, unmatched

# Streamlit UI
def main():
    st.title("📑 Construction Specifications Analyzer")
    
    # First dropdown for PDF selection
    pdf_names = get_unique_pdf_names()
    if not pdf_names:
        st.warning("No PDF documents found in database.")
        return

    pdf_options = ["-- Select a PDF --"] + pdf_names
    selected_pdf = st.selectbox(
        "1. Select a PDF document:",
        pdf_options
    )

    if selected_pdf == "-- Select a PDF --":
        st.info("Please select a PDF to proceed.")
        return

    # Second dropdown for section selection
    sections = get_sections_for_pdf(selected_pdf)
    if not sections:
        st.warning(f"No sections found in '{selected_pdf}'.")
        return

    section_options = ["-- Select a section --"] + sections
    selected_section = st.selectbox(
        "2. Select a section:",
        section_options
    )

    if selected_section == "-- Select a section --":
        st.info("Please select a section to proceed.")
        return

    if st.button("Analyze Section", type="primary"):
        with st.spinner(f"🔍 Analyzing {selected_section} from {selected_pdf}..."):
            content = get_section_content(selected_pdf, selected_section)
            if not content:
                st.error("No content found for this section.")
                return

            st.subheader(f"📌 Analysis Results")
            st.markdown(f"**PDF Document:** {selected_pdf}")
            st.markdown(f"**Section:** {selected_section}")
            
            manufacturer_output = get_manufacturers_info(content)
            
            st.markdown("---")
            st.subheader("🔧 Manufacturers Found")
            st.markdown(manufacturer_output)

            lines = manufacturer_output.splitlines()
            manufacturers = [line for line in lines if line.strip() and not line.lower().startswith("no manufacturer")]

            matched_neumann, matched_macaulay, unmatched = match_brands(manufacturers)

            st.markdown("---")
            st.subheader("🏷️ Brand Matching")
            if matched_neumann:
                st.success(f"**✅ Neumann Brands:** {', '.join(matched_neumann)}")
            if matched_macaulay:
                st.success(f"**✅ Macaulay Brands:** {', '.join(matched_macaulay)}")
            if unmatched:
                st.warning(f"**⚠️ Unmatched Manufacturers:** {', '.join(unmatched)}")

            with st.expander("📄 View Full Section Content", expanded=False):
                st.code(content[:10000] + ("..." if len(content) > 10000 else ""), language='text')

if __name__ == "__main__":
    main()
