import ryans
import json
import threading
import time
import os
import random
import re
import requests
from dotenv import load_dotenv
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)
load_dotenv()

# ==========================================
# BAGIAN 1: HELPER FUNGSI (UI & VALIDASI)
# ==========================================

def print_header(title):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*50}")
    print(f"{title.center(50)}")
    print(f"{'='*50}{Style.RESET_ALL}")

def ask_yes_no(question):
    """Meminta input y/n dengan validasi loop"""
    while True:
        response = input(f"{Fore.YELLOW}[?] {question} (y/n): {Style.RESET_ALL}").lower().strip()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print(f"{Fore.RED}    [!] Input salah! Harap ketik 'y' atau 'n'.{Style.RESET_ALL}")

def ask_choice(question, choices, default=None):
    """Meminta input pilihan string (misal: en/id)"""
    choices_str = "/".join(choices)
    while True:
        prompt = f"{Fore.YELLOW}[?] {question} ({choices_str})"
        if default:
            prompt += f" [Default: {default}]"
        prompt += f": {Style.RESET_ALL}"
        
        response = input(prompt).lower().strip()
        
        if not response and default:
            return default
        if response in choices:
            return response
        
        print(f"{Fore.RED}    [!] Pilihan tidak valid. Pilih antara: {choices_str}{Style.RESET_ALL}")

def ask_int(question, default=None, min_val=0):
    """Meminta input angka dengan validasi"""
    while True:
        prompt = f"{Fore.YELLOW}[?] {question}"
        if default is not None:
            prompt += f" [Default: {default}]"
        prompt += f": {Style.RESET_ALL}"
        
        response = input(prompt).strip()
        
        if not response and default is not None:
            return default
        
        if response.isdigit():
            val = int(response)
            if val >= min_val:
                return val
            else:
                print(f"{Fore.RED}    [!] Angka harus lebih besar dari {min_val}.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}    [!] Harap masukkan angka yang valid.{Style.RESET_ALL}")

# ==========================================
# BAGIAN 2: LOGIKA FILE CHAT MANUAL
# ==========================================
chat_lines = []
chat_index = 0

def load_chat_file():
    global chat_lines
    try:
        if os.path.exists("chat.txt"):
            with open("chat.txt", "r", encoding="utf-8") as file:
                chat_lines = [line.strip() for line in file.readlines() if line.strip()]
            print(f"{Fore.GREEN}[INFO] Berhasil memuat {len(chat_lines)} baris dari chat.txt")
        else:
            print(f"{Fore.RED}[ERROR] File chat.txt tidak ditemukan! Pastikan file ada di folder yang sama.")
    except Exception as e:
        print(f"{Fore.RED}[ERROR] Gagal membaca chat.txt: {e}")

def get_next_chat_message():
    global chat_index, chat_lines
    if not chat_lines:
        return "chat.txt kosong atau tidak ditemukan!"
    
    message = chat_lines[chat_index]
    chat_index += 1
    if chat_index >= len(chat_lines):
        chat_index = 0
    return message

# ==========================================
# BAGIAN 3: KONFIGURASI BOT & AI
# ==========================================

discord_tokens_env = os.getenv('DISCORD_TOKENS', '')
if discord_tokens_env:
    discord_tokens = [token.strip() for token in discord_tokens_env.split(',') if token.strip()]
else:
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        discord_tokens = []

google_api_keys = os.getenv('GOOGLE_API_KEYS', '').split(',')
google_api_keys = [key.strip() for key in google_api_keys if key.strip()]

# DAFTAR MODEL
AVAILABLE_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite"
]

current_model_index = 0
processed_message_ids = set()
used_api_keys = set()
last_generated_text = None
cooldown_time = 3600

last_message_timestamps = {}
my_last_sent_id = {}

INTRO_MSGS_ID = [
    "Halo semua, lagi pada bahas apa nih?",
    "Waduh sepi amat, muncul dulu ah.",
    "Hadirrr... sori baru muncul.",
    "Siang guys, lancar?",
    "Yo whatsup, ramein lah.",
    "Absen dulu gan."
]

INTRO_MSGS_EN = [
    "Yo what's up everyone?",
    "Hey guys, what's cooking?",
    "Just logged in, how's it going?",
    "Sup people.",
    "Morning/Evening all, let's chat.",
    "Here I am, what did I miss?"
]

def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime('%H:%M:%S')
    if level.upper() == "SUCCESS":
        color, icon = Fore.GREEN, "✅"
    elif level.upper() == "ERROR":
        color, icon = Fore.RED, "🚨"
    elif level.upper() == "WARNING":
        color, icon = Fore.YELLOW, "⚠️"
    elif level.upper() == "WAIT":
        color, icon = Fore.CYAN, "⏳"
    elif level.upper() == "TYPING":
        color, icon = Fore.MAGENTA, "⌨️"
    elif level.upper() == "REVIVE":
        color, icon = Fore.LIGHTYELLOW_EX, "🔥"
    else:
        color, icon = Fore.WHITE, "ℹ️"

    print(f"{color}[{timestamp}] {icon} {message}{Style.RESET_ALL}")

def get_active_model():
    global current_model_index
    if current_model_index < len(AVAILABLE_MODELS):
        return AVAILABLE_MODELS[current_model_index]
    return AVAILABLE_MODELS[0]

def switch_model():
    global current_model_index, used_api_keys
    if current_model_index < len(AVAILABLE_MODELS) - 1:
        current_model_index += 1
        used_api_keys.clear()
        new_model = AVAILABLE_MODELS[current_model_index]
        log_message(f"⚠️ Pindah ke Model Cadangan: {new_model}", "WARNING")
        return True
    return False

def get_random_api_key():
    global current_model_index
    available_keys = [key for key in google_api_keys if key not in used_api_keys]

    if not available_keys:
        log_message("⚠️ Semua API Key limit. Ganti model...", "WARNING")
        if switch_model():
            return get_random_api_key()
        else:
            log_message("🚨 SEMUA Key dan Model habis! Istirahat 1 jam...", "ERROR")
            time.sleep(cooldown_time)
            used_api_keys.clear()
            current_model_index = 0
            return get_random_api_key()

    return random.choice(available_keys)

def generate_language_specific_prompt(user_message, prompt_language):
    if prompt_language == 'id':
        return f"Konteks: Kamu user Discord santai. Balas teks ini (Indo gaul, lowercase, singkat, natural): \"{user_message}\""
    elif prompt_language == 'en':
        return f"Context: You are a chill Discord user. Reply to this (English slang, lowercase, short, vibe): \"{user_message}\""
    return None

def generate_reply(prompt, prompt_language, use_google_ai=True):
    global last_generated_text, used_api_keys

    # JIKA MENGGUNAKAN AI
    if use_google_ai:
        if not google_api_keys:
             return "Error: API Key Google belum disetting di .env"

        google_api_key = get_random_api_key()
        current_model = get_active_model()
        
        if prompt.startswith("SPECIAL:"):
            ai_prompt = prompt.replace("SPECIAL:", "").strip()
        else:
            lang_prompt = generate_language_specific_prompt(prompt, prompt_language)
            if lang_prompt is None: return None
            
            if prompt_language == 'en':
                style = "Instruction: Do not be formal. Use internet slang if appropriate. Keep it short (1 sentence). No quotes."
            else:
                style = "Instruksi: Jangan formal. Posisikan dirimu nimbrung obrolan. Jawab singkat (1 kalimat), huruf kecil semua, gak usah pake tanda kutip."
            ai_prompt = f"{lang_prompt}\n\n{style}"

        url = f'https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={google_api_key}'
        headers = {'Content-Type': 'application/json'}
        data = {'contents': [{'parts': [{'text': ai_prompt}]}]}

        while True:
            try:
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 404:
                    if switch_model(): return generate_reply(prompt, prompt_language, use_google_ai)
                    else: return None
                if response.status_code == 429:
                    used_api_keys.add(google_api_key)
                    return generate_reply(prompt, prompt_language, use_google_ai)
                if response.status_code == 503:
                    time.sleep(2)
                    continue

                response.raise_for_status()
                result = response.json()

                try:
                    candidates = result.get('candidates', [])
                    if candidates and 'content' in candidates[0]:
                        generated_text = candidates[0]['content']['parts'][0]['text'].strip()
                        generated_text = generated_text.replace('"', '').replace("'", "")
                        
                        if generated_text == last_generated_text: continue
                        last_generated_text = generated_text
                        return generated_text
                    else:
                        return "Waduh..."
                except Exception:
                    return None
            except requests.exceptions.RequestException:
                time.sleep(2)
                return generate_reply(prompt, prompt_language, use_google_ai)
    
    # JIKA TIDAK MENGGUNAKAN AI (MANUAL MODE)
    else:
        return get_next_chat_message()

# ==========================================
# BAGIAN 4: DISCORD API WRAPPER
# ==========================================

def get_channel_info(channel_id, token):
    headers = {'Authorization': token}
    try:
        res = requests.get(f"https://discord.com/api/v9/channels/{channel_id}", headers=headers)
        if res.status_code == 200:
            return res.json().get('name', 'Unknown'), res.json().get('name', 'Channel')
    except: pass
    return "Unknown Server", "Unknown Channel"

def get_bot_info(token):
    try:
        res = requests.get("https://discord.com/api/v9/users/@me", headers={'Authorization': token})
        if res.status_code == 200:
            data = res.json()
            return data.get("username"), data.get("discriminator"), data.get("id")
    except: return "Unknown", "", "Unknown"

def get_channel_slowmode(channel_id, token):
    try:
        res = requests.get(f"https://discord.com/api/v9/channels/{channel_id}", headers={'Authorization': token})
        if res.status_code == 200: return res.json().get("rate_limit_per_user", 0)
    except: pass
    return 0

def trigger_typing(channel_id, token, duration):
    try:
        requests.post(f"https://discord.com/api/v9/channels/{channel_id}/typing", headers={'Authorization': token})
        time.sleep(duration)
    except: time.sleep(duration)

def delete_message(channel_id, message_id, token):
    try:
        requests.delete(f'https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}', headers={'Authorization': token})
    except: pass

def send_message(channel_id, text, token, reply_to=None, delete_after=None, delete_immediately=False):
    payload = {'content': text}
    if reply_to: payload["message_reference"] = {"message_id": reply_to}

    slow_mode = get_channel_slowmode(channel_id, token)
    last_sent = last_message_timestamps.get(channel_id, 0)
    elapsed = time.time() - last_sent
    
    # Jika slowmode aktif, tunggu sampai aman
    if slow_mode > 0:
        remaining = slow_mode - elapsed
        if remaining > 0:
            wait_time = remaining + random.uniform(1.0, 2.0)
            log_message(f"Menunggu Slow Mode ({wait_time:.1f}s)...", "WAIT")
            time.sleep(wait_time)
        else:
            # Tetap kasih jeda natural meski sudah lewat waktunya
            time.sleep(random.uniform(1.5, 3.0))
    else:
        time.sleep(random.uniform(2.0, 4.5))

    typing_duration = min(len(text) * 0.12, 8.0) 
    
    log_message(f"Sedang mengetik... ({typing_duration:.1f}s)", "TYPING")
    trigger_typing(channel_id, token, typing_duration)

    try:
        res = requests.post(
            f"https://discord.com/api/v9/channels/{channel_id}/messages",
            json=payload, headers={'Authorization': token, 'Content-Type': 'application/json'}
        )
        
        if res.status_code in [200, 201]:
            msg_data = res.json()
            msg_id = msg_data.get("id")
            log_message(f"[Channel {channel_id}] Terkirim: \"{text}\"", "SUCCESS")
            
            last_message_timestamps[channel_id] = time.time()
            my_last_sent_id[channel_id] = msg_id 

            if delete_immediately:
                threading.Thread(target=delete_message, args=(channel_id, msg_id, token), daemon=True).start()
            elif delete_after and delete_after > 0:
                log_message(f"Hapus pesan dalam {delete_after}s...", "WAIT")
                threading.Thread(target=lambda: (time.sleep(delete_after), delete_message(channel_id, msg_id, token)), daemon=True).start()
            
            return msg_id 
        
        elif res.status_code == 429:
            retry = res.json().get('retry_after', 5)
            log_message(f"Rate Limit! Tunggu {retry}s", "ERROR")
            time.sleep(retry)
            return send_message(channel_id, text, token, reply_to, delete_after, delete_immediately)

    except Exception as e:
        log_message(f"[Channel {channel_id}] Gagal kirim: {e}", "ERROR")
    return None

def get_recent_chat_context(channel_id, token, limit=15, bot_id=None):
    headers = {'Authorization': token}
    try:
        res = requests.get(f'https://discord.com/api/v9/channels/{channel_id}/messages?limit={limit}', headers=headers)
        if res.status_code == 200:
            msgs = res.json()
            history_chat = []
            for m in reversed(msgs): 
                if m.get('content'):
                    user = m['author']['username']
                    if bot_id and m['author']['id'] == bot_id: user = "YOU (Me)"
                    history_chat.append(f"{user}: {m['content']}")
            return "\n".join(history_chat)
    except: pass
    return ""

# ==========================================
# BAGIAN 5: LOGIKA UTAMA BOT (LOOP)
# ==========================================

def auto_reply(channel_id, settings, token):
    headers = {'Authorization': token}
    bot_name, _, bot_id = get_bot_info(token)
    
    last_interaction_time = time.time()
    
    log_message(f"Bot start: {bot_name} di Channel {channel_id}", "SUCCESS")

    # --- MODE 1: MENGGUNAKAN AI ---
    if settings["use_google_ai"]:
        if settings["send_intro"]:
            startup_delay = random.uniform(5.0, 15.0)
            log_message(f"Menganalisa chat... (Tunggu {startup_delay:.1f}s)", "WAIT")
            time.sleep(startup_delay)

            context_str_intro = get_recent_chat_context(channel_id, token, 15, bot_id)
            intro_text = None
            
            if context_str_intro:
                if settings["prompt_language"] == 'id':
                    prompt_intro = f"SPECIAL:Riwayat chat:\n{context_str_intro}\nInstruksi: Kamu baru online. Buat 1 kalimat singkat (Indo gaul, lowercase) untuk NIMBRUNG topik di atas. Jangan kaku."
                else:
                    prompt_intro = f"SPECIAL:Chat history:\n{context_str_intro}\nInstruction: You just came online. Create 1 short, casual, lowercase sentence to JOIN the topic above."

                intro_text = generate_reply(prompt_intro, settings["prompt_language"], True)

            if not intro_text or "Waduh" in intro_text:
                intro_list = INTRO_MSGS_ID if settings["prompt_language"] == 'id' else INTRO_MSGS_EN
                intro_text = random.choice(intro_list)

            send_message(channel_id, intro_text, token, delete_after=settings["delete_bot_reply"])
            last_interaction_time = time.time()
            time.sleep(random.uniform(5, 10))

        # LOOP AI
        while True:
            current_time = time.time()
            time.sleep(settings["read_delay"] + random.uniform(0.5, 1.5))

            try:
                res = requests.get(f'https://discord.com/api/v9/channels/{channel_id}/messages?limit=30', headers=headers)
                if res.status_code == 200:
                    msgs = res.json()
                    
                    if msgs:
                        priority_queue = []
                        general_queue = []
                        
                        for msg in msgs:
                            m_id = msg['id']
                            author_id = msg['author']['id']
                            
                            if author_id == bot_id: continue
                            if m_id in processed_message_ids or msg['type'] == 8: continue

                            is_priority = False
                            if 'referenced_message' in msg and msg['referenced_message']:
                                if msg['referenced_message']['author']['id'] == bot_id:
                                    is_priority = True
                            if bot_id in msg.get('content', '') or f"@{bot_name}" in msg.get('content', ''):
                                is_priority = True
                                
                            if is_priority:
                                priority_queue.append(msg)
                            elif settings["auto_chat_mode"]:
                                general_queue.append(msg)

                        priority_queue.reverse()
                        general_queue.reverse()

                        processed_priority_count = 0
                        
                        for msg in priority_queue:
                            m_id = msg['id']
                            if m_id in processed_message_ids: continue
                            
                            processed_message_ids.add(m_id)
                            last_interaction_time = time.time()
                            processed_priority_count += 1
                            
                            content = msg.get('content', '').strip()
                            disp_content = (content[:50] + '...') if len(content) > 50 else content
                            log_message(f"🔔 Membalas Reply dari {msg['author']['username']}: \"{disp_content}\"", "WARNING")
                            
                            reply = generate_reply(content, settings["prompt_language"], True)
                            
                            if reply:
                                do_reply = settings["use_reply"] or True
                                send_message(channel_id, reply, token,
                                                reply_to=m_id if do_reply else None,
                                                delete_after=settings["delete_bot_reply"],
                                                delete_immediately=settings["delete_immediately"])
                                
                                if len(priority_queue) > 1:
                                    time.sleep(random.uniform(2.0, 4.0))

                        if processed_priority_count == 0 and general_queue:
                            msg = general_queue[-1] 
                            m_id = msg['id']
                            
                            if m_id not in processed_message_ids:
                                processed_message_ids.add(m_id)
                                last_interaction_time = time.time()
                                
                                content = msg.get('content', '').strip()
                                disp_content = (content[:50] + '...') if len(content) > 50 else content
                                log_message(f"Menanggapi chat {msg['author']['username']}: \"{disp_content}\" (Nimbrung)", "INFO")
                                
                                reply = generate_reply(content, settings["prompt_language"], True)
                                
                                if reply:
                                    do_reply = settings["use_reply"]
                                    send_message(channel_id, reply, token,
                                                     reply_to=m_id if do_reply else None,
                                                     delete_after=settings["delete_bot_reply"],
                                                     delete_immediately=settings["delete_immediately"])

                    if settings["auto_revive"] and (current_time - last_interaction_time > settings["revive_interval"]):
                        log_message(f"Chat sepi selama {settings['revive_interval']}s. Mencoba membangkitkan topik...", "REVIVE")
                        
                        context_str = get_recent_chat_context(channel_id, token, 15, bot_id)
                        
                        if context_str:
                            if settings["prompt_language"] == 'id':
                                prompt_revive = f"SPECIAL:Riwayat chat:\n{context_str}\nInstruksi: Chat berhenti. Lanjutkan diskusi dengan membuat pertanyaan atau pernyataan santai berdasarkan TOPIK TERAKHIR di atas. JANGAN menyapa ulang, JANGAN tanya 'kok sepi', langsung bahas kontennya. Gaya: santai, lowercase."
                            else:
                                prompt_revive = f"SPECIAL:Chat history:\n{context_str}\nInstruction: The chat went quiet. Create a casual follow-up question or statement based on the LAST TOPIC DISCUSSED to revive it. Do NOT ask 'why is it quiet'. Just continue the flow. Style: casual, lowercase."
                            
                            revive_msg = generate_reply(prompt_revive, settings["prompt_language"], True)
                            
                            if revive_msg and "Waduh" not in revive_msg:
                                send_message(channel_id, revive_msg, token, delete_after=settings["delete_bot_reply"])
                                last_interaction_time = time.time()
                            else:
                                log_message("Gagal generate revive message.", "ERROR")
                                last_interaction_time = time.time() + 60
                        else:
                            last_interaction_time = time.time()
                            
            except Exception as e:
                log_message(f"Error Loop AI: {e}", "ERROR")
                time.sleep(5)

    # --- MODE 2: MANUAL (CHAT.TXT) ---
    else:
        log_message(f"Mode Manual: Menyesuaikan delay dengan server...", "INFO")
        
        while True:
            # 1. Kirim pesan
            msg = generate_reply("", settings["prompt_language"], False)
            log_message(f"Mengirim pesan manual: {msg}", "INFO")
            
            # send_message sudah mengurus delay awal agar tidak rate limit saat mengirim
            send_message(channel_id, msg, token,
                         delete_after=settings["delete_bot_reply"],
                         delete_immediately=settings["delete_immediately"])
            
            # 2. Hitung Delay untuk pesan BERIKUTNYA
            # Ambil slowmode terbaru dari server
            current_slowmode = get_channel_slowmode(channel_id, token)
            
            # Logika Cerdas: Gunakan angka terbesar antara input user vs slowmode server
            # Jika user isi 16s, tapi server 120s -> bot tunggu 120s (biar aman)
            # Jika user isi 60s, tapi server 5s   -> bot tunggu 60s (biar santai)
            effective_delay = max(settings['delay_interval'], current_slowmode)
            
            # Tambah sedikit random buffer (2-5 detik) agar tidak pas banget dan terdeteksi bot
            final_wait = effective_delay + random.uniform(2.0, 5.0)
            
            log_message(f"Menunggu {final_wait:.1f}s (Server: {current_slowmode}s, User: {settings['delay_interval']}s)...", "WAIT")
            time.sleep(final_wait)

# ==========================================
# BAGIAN 6: SETUP SETTINGS (UI BARU)
# ==========================================

def get_server_settings(channel_id, channel_name):
    print_header(f"KONFIGURASI CHANNEL: {channel_name}")
    print(f"{Fore.LIGHTBLACK_EX}ID: {channel_id}{Style.RESET_ALL}\n")

    # 1. Konfigurasi AI
    use_ai = ask_yes_no("Gunakan Gemini AI?")
    
    # 2. Konfigurasi Bahasa
    lang = ask_choice("Bahasa Prompt", ['en', 'id'], default='id')

    # Default values
    send_intro = False
    read_delay = 3
    auto_chat = False
    auto_revive = False
    revive_interval = 600
    delay_interval = 60
    
    if use_ai:
        print(f"\n{Fore.CYAN}--- PENGATURAN AI ---{Style.RESET_ALL}")
        send_intro = ask_yes_no("Kirim pesan PEMBUKA (Contextual Intro) saat start?")
        read_delay = ask_int("Interval Cek Pesan (detik)", default=3)
        
        print(f"\n{Fore.CYAN}--- MODE INTERAKSI ---{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}   [y] = Rusuh/Nimbrung (Balas semua chat orang)")
        print(f"   [n] = Kalem (Hanya balas reply/mention){Style.RESET_ALL}")
        auto_chat = ask_yes_no("Aktifkan Mode Rusuh (Auto Chat)?")

        print(f"\n{Fore.CYAN}--- AUTO REVIVE (PEMBANGKIT TOPIK) ---{Style.RESET_ALL}")
        auto_revive = ask_yes_no("Aktifkan Auto Revive (Hidupkan chat mati)?")
        if auto_revive:
            revive_interval = ask_int("Berapa detik chat sepi sebelum bot muncul?", default=600)
    else:
        print(f"\n{Fore.CYAN}--- PENGATURAN MANUAL ---{Style.RESET_ALL}")
        print(f"{Fore.LIGHTBLACK_EX}(Bot akan otomatis mengikuti slowmode server jika lebih lama dari inputmu){Style.RESET_ALL}")
        delay_interval = ask_int("Delay MINIMUM chat manual (detik)", default=60)

    print(f"\n{Fore.CYAN}--- PENGATURAN UMUM ---{Style.RESET_ALL}")
    use_reply = ask_yes_no("Gunakan fitur Reply (Quote) chat orang?")

    del_after = None
    del_now = False
    
    if ask_yes_no("Hapus pesan balasan bot otomatis?"):
        print(f"{Fore.LIGHTBLACK_EX}   (0 = Hapus secepat kilat / Flash){Style.RESET_ALL}")
        del_val = ask_int("Hapus setelah berapa detik?", default=0)
        
        if del_val == 0:
            del_now = True
        else:
            del_after = del_val

    print(f"\n{Fore.GREEN}[SUCCESS] Konfigurasi untuk {channel_name} tersimpan!{Style.RESET_ALL}")
    time.sleep(1) 
    
    return {
        "use_google_ai": use_ai, 
        "prompt_language": lang,
        "send_intro": send_intro,
        "read_delay": read_delay,
        "auto_chat_mode": auto_chat,
        "auto_revive": auto_revive,
        "revive_interval": revive_interval,
        "delay_interval": delay_interval, 
        "use_reply": use_reply,
        "delete_bot_reply": del_after, 
        "delete_immediately": del_now
    }

# ==========================================
# BAGIAN 7: EKSEKUSI UTAMA
# ==========================================

if __name__ == "__main__":
    try:
        ryans.banner()
    except Exception as e:
        print(f"Error loading Ryans Banner: {e}")
    
    # Load chat file di awal
    load_chat_file()
        
    bot_details = []
    for t in discord_tokens:
        u, d, i = get_bot_info(t)
        bot_details.append(f"{u}#{d}")
        log_message(f"Login sebagai: {u}#{d}", "SUCCESS")

    raw_ids = input("\nMasukkan Channel ID (pisahkan koma): ").split(',')
    channel_ids = [x.strip() for x in raw_ids if x.strip()]

    threads = []
    for i, cid in enumerate(channel_ids):
        active_token = discord_tokens[i % len(discord_tokens)]
        s_name, c_name = get_channel_info(cid, active_token)
        settings = get_server_settings(cid, c_name)

        t = threading.Thread(target=auto_reply, args=(cid, settings, active_token))
        t.daemon = True
        threads.append(t)

        log_message(f"Menyiapkan thread untuk {c_name}...", "INFO")

    print(f"\n{Fore.GREEN}=== MEMULAI SEMUA BOT ==={Style.RESET_ALL}")
    for t in threads:
        t.start()
        time.sleep(1)

    try:
        while True: time.sleep(10)
    except KeyboardInterrupt:
        print("\nBot dimatikan.")
