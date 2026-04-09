import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import pytz
from datetime import datetime
import time
import base64
import streamlit.components.v1 as components

# -------------------
# Import shared modules
# -------------------
from config import (
    WEATHER_API_KEY, FIREBASE_URL, STOCK_TICKERS, CITIES, TIMEZONES,
    DEFAULT_USER_ID, AES_BLOCK_SIZE, validate_config
)
from utils.crypto_utils import (
    aes_encrypt, aes_decrypt, aes_encrypt_decrypt, des_encrypt_decrypt,
    aes_cbc_encrypt_decrypt, des_cbc_encrypt_decrypt,
    ecb_vs_cbc_demo, hash_sha256, hash_md5,
    encrypt_portfolio_for_firebase, pad
)
from utils.firebase_utils import read_user_data, write_user_data, patch_user_data

# -------------------
# Page Setup
# -------------------
st.set_page_config(page_title="🔐 PoCS Secure Dashboard", page_icon="🛡️", layout="wide")

# -------------------
# Check config warnings
# -------------------
config_warnings = validate_config()
for w in config_warnings:
    st.sidebar.warning(f"⚠️ {w}")

# -------------------
# CSS Styling
# -------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main-header {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    padding: 1.5rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    text-align: center;
}
.main-header h1 {
    color: #fff;
    font-size: 2rem;
    margin: 0;
    text-shadow: 0 0 20px rgba(0,255,179,0.4);
}
.main-header p {
    color: #aaa;
    font-size: 0.95rem;
    margin: 0.3rem 0 0 0;
}

.delta-red { color: #ff4d4d; font-weight: 600; }
.delta-green { color: #00c853; font-weight: 600; }
.metric-compact { margin-bottom: 0.4rem; }

.clock {
    font-size: 1.4rem;
    font-weight: 600;
    color: #00FFB3;
    text-shadow: 0 0 10px #00FFB3;
}

.card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(10px);
}

.section-title {
    font-size: 1.3rem;
    font-weight: 600;
    margin-bottom: 0.8rem;
    color: #e0e0e0;
}

.portfolio-success {
    background: linear-gradient(135deg, #00c853, #00e676);
    color: #000;
    padding: 0.8rem 1.2rem;
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# -------------------
# Header
# -------------------
st.markdown("""
<div class="main-header">
    <h1>🛡️ Real-Time Secure Dashboard</h1>
    <p>RFID-Based Portfolio Management | AES-128 Encryption | IoT + Cybersecurity</p>
</div>
""", unsafe_allow_html=True)

# -------------------
# Navigation Tabs
# -------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "🌦️ Weather & Time",
    "💹 Live Stocks",
    "🔐 Portfolio Manager",
    "⚔️ AES vs DES Analysis"
])

# ============================================================
# TAB 1: WEATHER & GLOBAL TIMES
# ============================================================
with tab1:
    st.markdown('<div class="section-title">🌦️ Global Weather & Times</div>', unsafe_allow_html=True)

    def fetch_weather(city):
        try:
            clean_key = WEATHER_API_KEY.strip()
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={clean_key}&units=metric"
            res = requests.get(url, timeout=5)
            data = res.json()
            if res.status_code != 200:
                return None, None, None
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"].title()
            icon = data["weather"][0]["icon"]
            return temp, desc, icon
        except Exception:
            return None, None, None

    weather_data = {c: fetch_weather(c) for c in CITIES}

    wc1, wc2, wc3, wc4 = st.columns(4)
    cols = [wc1, wc2, wc3]

    for col, city in zip(cols, CITIES):
        temp, desc, icon = weather_data[city]
        tz_name = TIMEZONES[city]

        with col:
            st.markdown(f"**{city}**")
            components.html(f"""
                <div style="font-size:1.4rem;font-weight:600;color:#00FFB3;text-shadow:0 0 10px #00FFB3;">
                    🕒 <span id="{city.replace(' ', '_')}_clock"></span>
                </div>
                <script>
                function updateClock_{city.replace(' ', '_')}() {{
                    const now = new Date();
                    const options = {{
                        hour: '2-digit', minute: '2-digit', second: '2-digit',
                        hour12: true, timeZone: '{tz_name}'
                    }};
                    document.getElementById("{city.replace(' ', '_')}_clock").textContent =
                        now.toLocaleTimeString([], options);
                }}
                setInterval(updateClock_{city.replace(' ', '_')}, 1000);
                updateClock_{city.replace(' ', '_')}();
                </script>
            """, height=45)

            if temp is not None:
                st.image(f"http://openweathermap.org/img/wn/{icon}@2x.png", width=60)
                st.markdown(f"🌡️ {temp:.1f}°C — {desc}")
            else:
                st.markdown("❌ Weather unavailable")

    with wc4:
        st.markdown("**Local Device Time**")
        components.html("""
            <div style="font-size:1.4rem;font-weight:600;color:#00FFB3;text-shadow:0 0 10px #00FFB3;">
                🕒 <span id="local_clock"></span>
            </div>
            <script>
            function updateLocalClock() {
                const now = new Date();
                const t = now.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:true});
                document.getElementById("local_clock").textContent = t;
            }
            setInterval(updateLocalClock, 1000);
            updateLocalClock();
            </script>
        """, height=50)


# ============================================================
# TAB 2: LIVE STOCK PRICES
# ============================================================
with tab2:
    st.markdown('<div class="section-title">💹 Live Indian Stock Prices (Yahoo Finance)</div>', unsafe_allow_html=True)

    def fetch_stock_price(symbol):
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")
            if data.empty:
                return None, None, None
            latest_price = data["Close"].iloc[-1]
            open_price = data["Open"].iloc[0]
            prev_close = ticker.history(period="2d", interval="1d")["Close"].iloc[-2]
            return latest_price, open_price, prev_close
        except Exception:
            return None, None, None

    if "prices" not in st.session_state:
        st.session_state.prices = {t: [] for t in STOCK_TICKERS}
        st.session_state.timestamps = []

    stock_cols = st.columns(len(STOCK_TICKERS))

    for i, t in enumerate(STOCK_TICKERS):
        current, open_price, prev_close = fetch_stock_price(t)
        if current is None:
            with stock_cols[i]:
                st.warning(f"{t}: Data unavailable")
            continue

        st.session_state.prices[t].append(current)
        if i == 0:
            st.session_state.timestamps.append(pd.Timestamp.now())

        change = current - prev_close
        pct_change = (change / prev_close) * 100 if prev_close else 0
        delta_color_class = "delta-green" if change >= 0 else "delta-red"
        arrow = "🟢⬆️" if change > 0 else "🔴⬇️" if change < 0 else "⚪"

        with stock_cols[i]:
            st.markdown(f"""
            <div class="card">
                <b>{t.replace('.NS', '')}</b><br>
                <span style="font-size:1.8rem;font-weight:700;">₹{current:.2f}</span><br>
                <span class="{delta_color_class}">{arrow} {change:+.2f} ({pct_change:+.2f}%)</span>
            </div>
            """, unsafe_allow_html=True)

    # Stock chart
    if len(st.session_state.timestamps) > 1:
        st.markdown("### 📈 Price History")
        min_len = min([len(st.session_state.timestamps)] + [len(st.session_state.prices[t]) for t in STOCK_TICKERS])
        trimmed_timestamps = st.session_state.timestamps[:min_len]
        df = pd.DataFrame(index=trimmed_timestamps)
        for t in STOCK_TICKERS:
            df[t.replace('.NS', '')] = st.session_state.prices[t][:min_len]
        st.line_chart(df)


# ============================================================
# TAB 3: PORTFOLIO MANAGER (RFID + AES + Firebase)
# ============================================================
with tab3:
    st.markdown('<div class="section-title">🔐 Secure Portfolio Manager</div>', unsafe_allow_html=True)
    st.markdown("""
    Enter your RFID UID and portfolio data below. The portfolio will be **AES-128 encrypted** 
    and stored securely in **Firebase Realtime Database**. Only the matching RFID card on the 
    ESP32 can decrypt and display this data.
    """)

    st.markdown("---")

    col_write, col_read = st.columns(2)

    # --- WRITE PORTFOLIO ---
    with col_write:
        st.markdown("### ✍️ Store Encrypted Portfolio")

        rfid_uid = st.text_input(
            "RFID UID (e.g., UID12345)",
            value=DEFAULT_USER_ID,
            help="This must match the RFID card UID registered on your ESP32"
        )

        portfolio_text = st.text_area(
            "Portfolio Data",
            value="BTC=0.25, ETH=1.5, SOL=10",
            help="Enter your portfolio holdings. This will be encrypted with AES-128."
        )

        # AES key input — must match the key on ESP32
        aes_key_input = st.text_input(
            "AES-128 Key (16 characters)",
            value="1234567890abcdef",
            type="password",
            help="This 16-character key must be the SAME on both Streamlit and ESP32 sides."
        )

        if st.button("🔒 Encrypt & Store to Firebase", type="primary"):
            # Validation
            if not rfid_uid.strip():
                st.error("❌ Please enter an RFID UID.")
            elif not portfolio_text.strip():
                st.error("❌ Please enter portfolio data.")
            elif len(aes_key_input) != 16:
                st.error("❌ AES key must be exactly 16 characters (128-bit).")
            else:
                try:
                    aes_key = aes_key_input.encode('utf-8')

                    # 1. Fetch AI Strategy via Gemini Local Integration
                    portfolio_text_with_ai = portfolio_text
                    try:
                        import google.generativeai as genai
                        from config import GEMINI_API_KEY
                        
                        if GEMINI_API_KEY:
                            genai.configure(api_key=GEMINI_API_KEY)
                            model = genai.GenerativeModel('gemini-2.5-flash')
                            
                            prompt = f"Given this user portfolio: {portfolio_text}, provide a 14-character max actionable strategy. E.g. 'HOLD Mkt Volatile' or 'SELL BTC NOW'. Output nothing else."
                            response = model.generate_content(prompt)
                            ai_text = response.text.replace("\n", "").strip()[:15]
                            portfolio_text_with_ai = f"{portfolio_text} | AI: {ai_text}"
                            st.success(f"🤖 AI Edge Strategy Generated: {ai_text}")
                    except Exception as e:
                        st.warning(f"AI Advisor temporarily unavailable: {e}")

                    # 2. Encrypt using AES
                    encrypted_b64 = encrypt_portfolio_for_firebase(portfolio_text_with_ai, aes_key)

                    # Store to Firebase
                    data = {
                        "portfolio_AES": encrypted_b64,
                        "last_updated": datetime.now().isoformat(),
                    }
                    status = patch_user_data(rfid_uid, data)

                    if status == 200:
                        st.success("✅ Portfolio encrypted and stored to Firebase!")
                        
                        st.markdown("**🧠 AI Appended Strategy:**")
                        st.info(portfolio_text_with_ai)

                        st.markdown("**Encrypted output (Base64):**")
                        st.code(encrypted_b64, language="text")
                        st.info(f"📍 Stored at: `/users/{rfid_uid}/portfolio_AES`")
                    else:
                        st.error(f"❌ Firebase write failed with status {status}")
                except Exception as e:
                    st.error(f"❌ Encryption error: {e}")

    # --- READ & DECRYPT PORTFOLIO ---
    with col_read:
        st.markdown("### 🔓 Read & Decrypt Portfolio")

        read_uid = st.text_input(
            "RFID UID to read",
            value=DEFAULT_USER_ID,
            key="read_uid"
        )

        read_key = st.text_input(
            "AES-128 Key (16 characters)",
            value="1234567890abcdef",
            type="password",
            key="read_key"
        )

        if st.button("📖 Fetch & Decrypt from Firebase"):
            if not read_uid.strip():
                st.error("❌ Please enter an RFID UID.")
            elif len(read_key) != 16:
                st.error("❌ AES key must be exactly 16 characters.")
            else:
                try:
                    user_data = read_user_data(read_uid)

                    if user_data and "portfolio_AES" in user_data:
                        encrypted_b64 = user_data["portfolio_AES"]
                        st.markdown("**Encrypted (from Firebase):**")
                        st.code(encrypted_b64, language="text")

                        # Decrypt
                        aes_key = read_key.encode('utf-8')
                        decrypted, dec_time = aes_decrypt(encrypted_b64, aes_key)

                        st.markdown("**🔓 Decrypted Portfolio:**")
                        st.markdown(f'<div class="portfolio-success">{decrypted}</div>', unsafe_allow_html=True)
                        st.caption(f"Decryption time: {dec_time:.4f} ms")

                        # Show last updated
                        if "last_updated" in user_data:
                            st.caption(f"Last updated: {user_data['last_updated']}")
                    elif user_data:
                        st.warning("⚠️ User found but no portfolio_AES data.")
                        st.json(user_data)
                    else:
                        st.error(f"❌ No data found for UID: {read_uid}")
                except Exception as e:
                    st.error(f"❌ Decryption failed: {e}")
                    st.info("💡 Make sure you're using the same AES key that was used for encryption.")


# ============================================================
# TAB 4: AES vs DES ANALYSIS (Enhanced with CBC, Hashing)
# ============================================================
with tab4:
    st.markdown('<div class="section-title">⚔️ AES vs DES Encryption Analysis</div>', unsafe_allow_html=True)
    st.markdown("""
    Compare the **performance** and **security** of AES vs DES across multiple 
    encryption modes (ECB & CBC), plus SHA-256 vs MD5 hashing analysis.
    """)

    analysis_tab1, analysis_tab2, analysis_tab3 = st.tabs([
        "🔐 AES vs DES (ECB)",
        "🔄 ECB vs CBC Mode",
        "#️⃣ SHA-256 vs MD5 Hashing"
    ])

    # ---------- SUB-TAB 1: AES vs DES ECB ----------
    with analysis_tab1:
        st.markdown("---")
        user_text = st.text_area(
            "✍️ Enter text to encrypt:",
            "This is a secret message for the PoCS project!",
            key="crypto_input"
        )

        if st.button("⚡ Encrypt & Compare", type="primary", key="crypto_btn"):
            if user_text.strip() == "":
                st.warning("Please enter a message to encrypt.")
            else:
                aes_ct, aes_pt, aes_enc_time, aes_dec_time = aes_encrypt_decrypt(user_text)
                des_ct, des_pt, des_enc_time, des_dec_time = des_encrypt_decrypt(user_text)

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("### 🟢 AES-128-ECB")
                    st.metric("Encryption Time", f"{aes_enc_time:.6f} ms")
                    st.metric("Decryption Time", f"{aes_dec_time:.6f} ms")
                    st.markdown("**Ciphertext (Base64):**")
                    st.code(aes_ct[:200] + ("..." if len(aes_ct) > 200 else ""), language="text")
                    st.markdown(f"🔓 **Decrypted:** `{aes_pt}`")

                with col2:
                    st.markdown("### 🔴 DES-ECB")
                    st.metric("Encryption Time", f"{des_enc_time:.6f} ms")
                    st.metric("Decryption Time", f"{des_dec_time:.6f} ms")
                    st.markdown("**Ciphertext (Base64):**")
                    st.code(des_ct[:200] + ("..." if len(des_ct) > 200 else ""), language="text")
                    st.markdown(f"🔓 **Decrypted:** `{des_pt}`")

                # Performance comparison
                st.markdown("---")
                st.markdown("### 📊 Performance Comparison")

                total_aes = aes_enc_time + aes_dec_time
                total_des = des_enc_time + des_dec_time

                perf_df = pd.DataFrame({
                    "Algorithm": ["AES-128", "DES"],
                    "Encryption (ms)": [aes_enc_time, des_enc_time],
                    "Decryption (ms)": [aes_dec_time, des_dec_time],
                    "Total (ms)": [total_aes, total_des]
                })
                st.dataframe(perf_df.set_index("Algorithm"), use_container_width=True)

                st.bar_chart(
                    pd.DataFrame({
                        "AES-128 (ms)": [total_aes],
                        "DES (ms)": [total_des]
                    })
                )

                if total_aes < total_des:
                    st.success("✅ AES is faster — modern, optimized with hardware acceleration (AES-NI).")
                elif total_aes > total_des:
                    st.warning("⚠️ DES was faster in this run — likely due to timing jitter or small input.")
                else:
                    st.info("Both performed equally in this run.")

                # Security comparison table
                st.markdown("---")
                st.markdown("### 🛡️ Security Comparison")

                sec_df = pd.DataFrame({
                    "Property": [
                        "Key Length", "Block Size", "Rounds", "Status",
                        "Brute-Force Resistance", "Hardware Acceleration"
                    ],
                    "AES-128": [
                        "128 bits", "128 bits", "10", "✅ Current Standard (NIST FIPS 197)",
                        "2¹²⁸ operations", "✅ AES-NI instruction set"
                    ],
                    "DES": [
                        "56 bits (effective)", "64 bits", "16", "❌ Deprecated (since 2005)",
                        "2⁵⁶ operations (~1 day)", "❌ No hardware support"
                    ]
                })
                st.dataframe(sec_df.set_index("Property"), use_container_width=True)

                st.markdown("""
                #### 🔍 Why AES is Superior
                - **Key space**: AES-128 has 2¹²⁸ possible keys vs DES's 2⁵⁶ — making brute-force attacks computationally infeasible
                - **Block size**: AES's 128-bit blocks prevent birthday attacks that affect DES's 64-bit blocks
                - **NIST approved**: AES is the current U.S. federal encryption standard (FIPS 197)
                - **Hardware support**: Modern CPUs include AES-NI instructions for near-native speed
                - **DES was cracked**: In 1999, DES was broken in 22 hours by distributed computing
                """)

    # ---------- SUB-TAB 2: ECB vs CBC MODE COMPARISON ----------
    with analysis_tab2:
        st.markdown("---")
        st.markdown("""
        **ECB (Electronic Codebook)** encrypts each block independently.  
        **CBC (Cipher Block Chaining)** chains blocks together using an IV (Initialization Vector).  
        This demo shows why CBC is more secure than ECB.
        """)

        ecb_cbc_text = st.text_area(
            "✍️ Enter text for ECB vs CBC demo:",
            "AAAAAAAAAAAAAAAA AAAAAAAAAAAAAAAA",
            key="ecb_cbc_input",
            help="Try repeating patterns to see the ECB weakness!"
        )

        if st.button("🔬 Run ECB vs CBC Demo", type="primary", key="ecb_cbc_btn"):
            if ecb_cbc_text.strip() == "":
                st.warning("Please enter text.")
            else:
                # ECB vs CBC demo
                demo = ecb_vs_cbc_demo(ecb_cbc_text)

                st.markdown("### 🧪 Same Plaintext, Same Key — 3 Encryption Runs")

                col_ecb, col_cbc = st.columns(2)

                with col_ecb:
                    st.markdown("#### ECB Mode (No IV)")
                    for i, ct in enumerate(demo['ecb_results']):
                        st.code(f"Run {i+1}: {ct[:60]}...", language="text")

                    if demo['ecb_all_same']:
                        st.error("❌ ALL 3 runs produced IDENTICAL ciphertext!")
                        st.markdown("""
                        > **This is the ECB weakness**: identical plaintext blocks always 
                        > produce identical ciphertext blocks, leaking patterns in the data.
                        > This is known as the **'ECB Penguin Problem'**.
                        """)
                    else:
                        st.warning("Results varied (unexpected for ECB with same key).")

                with col_cbc:
                    st.markdown("#### CBC Mode (Random IV)")
                    for i, ct in enumerate(demo['cbc_results']):
                        st.code(f"Run {i+1}: {ct[:60]}...", language="text")

                    if demo['cbc_all_different']:
                        st.success("✅ ALL 3 runs produced DIFFERENT ciphertext!")
                        st.markdown("""
                        > **CBC is secure**: even with the same plaintext and key, 
                        > the random IV ensures every encryption produces unique output.
                        > An attacker cannot detect patterns.
                        """)
                    else:
                        st.info("Some results matched (extremely rare with random IVs).")

                # AES-CBC vs DES-CBC timing
                st.markdown("---")
                st.markdown("### ⏱️ AES-CBC vs DES-CBC Performance")

                aes_cbc_ct, aes_cbc_pt, aes_cbc_enc, aes_cbc_dec, aes_iv = aes_cbc_encrypt_decrypt(ecb_cbc_text)
                des_cbc_ct, des_cbc_pt, des_cbc_enc, des_cbc_dec, des_iv = des_cbc_encrypt_decrypt(ecb_cbc_text)

                cbc_df = pd.DataFrame({
                    "Algorithm": ["AES-128-CBC", "DES-CBC"],
                    "Encryption (ms)": [aes_cbc_enc, des_cbc_enc],
                    "Decryption (ms)": [aes_cbc_dec, des_cbc_dec],
                    "IV Used": [aes_iv[:16] + "...", des_iv],
                    "Decrypted Correctly": [
                        "✅" if aes_cbc_pt == ecb_cbc_text else "❌",
                        "✅" if des_cbc_pt == ecb_cbc_text else "❌"
                    ]
                })
                st.dataframe(cbc_df.set_index("Algorithm"), use_container_width=True)

                # ECB vs CBC comparison table
                st.markdown("---")
                st.markdown("### 📋 ECB vs CBC Summary")
                mode_df = pd.DataFrame({
                    "Property": [
                        "Uses IV?", "Block Independence", "Pattern Leakage",
                        "Parallelizable?", "Error Propagation", "Security Level"
                    ],
                    "ECB": [
                        "❌ No", "Each block encrypted independently",
                        "❌ Identical blocks → identical ciphertext",
                        "✅ Yes (faster)", "Single block only", "⚠️ Weak"
                    ],
                    "CBC": [
                        "✅ Yes (random IV)", "Each block depends on previous",
                        "✅ No pattern leakage",
                        "❌ No (sequential)", "Propagates to next block", "✅ Strong"
                    ]
                })
                st.dataframe(mode_df.set_index("Property"), use_container_width=True)

    # ---------- SUB-TAB 3: SHA-256 vs MD5 HASHING ----------
    with analysis_tab3:
        st.markdown("---")
        st.markdown("""
        **Hashing** is a one-way function that converts data into a fixed-size digest.  
        Unlike encryption, hashing **cannot be reversed**. It's used for:
        - Password storage
        - Data integrity verification
        - Digital signatures
        """)

        hash_text = st.text_area(
            "✍️ Enter text to hash:",
            "BTC=0.25, ETH=1.5",
            key="hash_input"
        )

        if st.button("🔨 Compute Hashes", type="primary", key="hash_btn"):
            if hash_text.strip() == "":
                st.warning("Please enter text.")
            else:
                sha_hash, sha_time = hash_sha256(hash_text)
                md5_hash, md5_time = hash_md5(hash_text)

                col_sha, col_md5 = st.columns(2)

                with col_sha:
                    st.markdown("### 🟢 SHA-256 (Secure)")
                    st.metric("Hash Time", f"{sha_time:.6f} ms")
                    st.markdown("**Digest (64 hex chars):**")
                    st.code(sha_hash, language="text")
                    st.markdown(f"**Length:** {len(sha_hash)} characters ({len(sha_hash)*4} bits)")

                with col_md5:
                    st.markdown("### 🔴 MD5 (Broken)")
                    st.metric("Hash Time", f"{md5_time:.6f} ms")
                    st.markdown("**Digest (32 hex chars):**")
                    st.code(md5_hash, language="text")
                    st.markdown(f"**Length:** {len(md5_hash)} characters ({len(md5_hash)*4} bits)")

                # Avalanche effect demo
                st.markdown("---")
                st.markdown("### 🌊 Avalanche Effect Demo")
                st.markdown("Changing just **1 character** should completely change the hash:")

                modified_text = hash_text[:-1] + chr(ord(hash_text[-1]) + 1) if hash_text else "a"

                sha_orig, _ = hash_sha256(hash_text)
                sha_mod, _ = hash_sha256(modified_text)
                md5_orig, _ = hash_md5(hash_text)
                md5_mod, _ = hash_md5(modified_text)

                st.markdown(f"**Original:** `{hash_text}`")
                st.markdown(f"**Modified:** `{modified_text}`")

                av_col1, av_col2 = st.columns(2)
                with av_col1:
                    st.markdown("**SHA-256:**")
                    st.code(f"Original: {sha_orig}\nModified: {sha_mod}", language="text")
                    # Count differing characters
                    diff_count = sum(1 for a, b in zip(sha_orig, sha_mod) if a != b)
                    st.markdown(f"**{diff_count}/{len(sha_orig)}** characters changed ({diff_count/len(sha_orig)*100:.1f}%)")

                with av_col2:
                    st.markdown("**MD5:**")
                    st.code(f"Original: {md5_orig}\nModified: {md5_mod}", language="text")
                    diff_count_md5 = sum(1 for a, b in zip(md5_orig, md5_mod) if a != b)
                    st.markdown(f"**{diff_count_md5}/{len(md5_orig)}** characters changed ({diff_count_md5/len(md5_orig)*100:.1f}%)")

                # Comparison table
                st.markdown("---")
                st.markdown("### 📋 SHA-256 vs MD5 Comparison")
                hash_comp_df = pd.DataFrame({
                    "Property": [
                        "Output Size", "Speed", "Collision Resistance",
                        "Status", "Use Case", "Known Vulnerabilities"
                    ],
                    "SHA-256": [
                        "256 bits (64 hex)", "Moderate", "✅ No known collisions",
                        "✅ Current standard (NIST)", "Passwords, blockchain, TLS",
                        "None known"
                    ],
                    "MD5": [
                        "128 bits (32 hex)", "Fast", "❌ Collisions found (2004)",
                        "❌ Broken / Deprecated", "Legacy checksums only",
                        "Collision attacks in seconds"
                    ]
                })
                st.dataframe(hash_comp_df.set_index("Property"), use_container_width=True)

                st.markdown("""
                #### ⚠️ Why MD5 is Dangerous
                - In **2004**, researchers demonstrated practical collision attacks on MD5
                - In **2008**, researchers created a rogue CA certificate using MD5 collisions
                - MD5 should **never** be used for security-critical applications
                - SHA-256 (part of SHA-2 family) remains secure and is used in Bitcoin, TLS, and more
                """)


# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#888; font-size:0.85rem;">
    🛡️ PoCS Project 2026 | Real-Time Secure Dashboard with RFID-Based Portfolio & Price Alerts<br>
    <span style="color:#555;">AES-128 Encryption | ESP32 + MFRC522 RFID | Firebase Realtime Database</span>
</div>
""", unsafe_allow_html=True)