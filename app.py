import streamlit as st
import psycopg2
from psycopg2 import sql
from groq import Groq
import os
from dotenv import load_dotenv
import concurrent.futures
import textwrap

# Load .env variables
load_dotenv()

# Initialize Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Manufacturer brand lists
neumann_brands = [...]
macaulay_brands = [...]

# Database connection
def get_db_connection():
    return psycopg2.connect(
        "postgresql://neondb_owner:npg_noGpAjWE04ym@ep-fragrant-forest-a5ikkddc-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    )

@st.cache_data
def get_all_section_names():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT section_name FROM pdf ORDER BY section_name")
            return [row[0] for row in cursor.fetchall()]

@st.cache_data
def get_section_content(section_name):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT content FROM pdf WHERE section_name = %s", (section_name,))
            result = cursor.fetchone()
            return result[0] if result else None

# Split large content for concurrent API calls
def split_content_for_api(content, chunk_token_limit=3000):
    # Rough approximation: 1 token ≈ 4 characters
    char_limit = chunk_token_limit * 4
    return textwrap.wrap(content, char_limit, break_long_words=False, replace_whitespace=False)

# API call for one chunk
def extract_manufacturers_chunk(chunk):
    try:
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
    st.markdown("""
        <style>
        #MainMenu, header, footer {
            visibility: hidden;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("🔧 Construction Specifications Analyzer")
    st.markdown("### Extract manufacturer info from any section")

    sections = get_all_section_names()
    if not sections:
        st.warning("No sections found in database.")
        return

    selected_section = st.selectbox("Select a section:", sections)

    if st.button("Get Manufacturer Information"):
        with st.spinner(f"Analyzing {selected_section}..."):
            content = get_section_content(selected_section)
            if not content:
                st.error("No content found for this section.")
                return

            manufacturer_output = get_manufacturers_info(content)
            st.subheader(f"Manufacturers Found in {selected_section}")
            st.markdown(manufacturer_output)

            # Parse and match manufacturers
            lines = manufacturer_output.splitlines()
            manufacturers = [line for line in lines if line.strip() and not line.lower().startswith("no manufacturer")]

            matched_neumann, matched_macaulay, unmatched = match_brands(manufacturers)

            st.markdown("#### ✅ Matches Found:")
            if matched_neumann:
                st.success(f"**Neumann Brands:** {', '.join(matched_neumann)}")
            if matched_macaulay:
                st.success(f"**Macaulay Brands:** {', '.join(matched_macaulay)}")
            if unmatched:
                st.warning("Some manufacturers not in either brand list.")

            with st.expander("📄 View Full Section Content"):
                st.code(content[:10000] + ("..." if len(content) > 10000 else ""), language='text')

if __name__ == "__main__":
    main()
