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

discord_tokens_env = os.getenv('DISCORD_TOKENS', '')
if discord_tokens_env:
    discord_tokens = [token.strip() for token in discord_tokens_env.split(',') if token.strip()]
else:
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        raise ValueError("Tidak ada Discord token! Atur DISCORD_TOKENS atau DISCORD_TOKEN di .env.")
    discord_tokens = [discord_token]

google_api_keys = os.getenv('GOOGLE_API_KEYS', '').split(',')
google_api_keys = [key.strip() for key in google_api_keys if key.strip()]
if not google_api_keys:
    raise ValueError("Tidak ada Google API Key! Atur GOOGLE_API_KEYS di .env.")

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

def get_random_message_from_file():
    try:
        with open("pesan.txt", "r", encoding="utf-8") as file:
            messages = [line.strip() for line in file.readlines() if line.strip()]
            return random.choice(messages) if messages else "Tidak ada pesan tersedia di file."
    except FileNotFoundError:
        return "File pesan.txt tidak ditemukan!"

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

    if use_google_ai:
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
    else:
        return get_random_message_from_file()

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
    
    if slow_mode > 0:
        remaining = slow_mode - elapsed
        wait_time = max(0, remaining) + random.uniform(1.5, 3.5)
        if remaining > 0: log_message(f"Menunggu Antrian Slow Mode ({remaining:.1f}s)...", "WAIT")
    else:
        wait_time = random.uniform(2.0, 4.5)

    typing_duration = min(len(text) * 0.12, 8.0) 
    
    if wait_time > typing_duration:
        time.sleep(wait_time - typing_duration)
        log_message(f"Sedang mengetik... ({typing_duration:.1f}s)", "TYPING")
        trigger_typing(channel_id, token, typing_duration)
    else:
        log_message(f"Sedang mengetik... ({wait_time:.1f}s)", "TYPING")
        trigger_typing(channel_id, token, wait_time)

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

def auto_reply(channel_id, settings, token):
    headers = {'Authorization': token}
    bot_name, _, bot_id = get_bot_info(token)
    
    last_interaction_time = time.time()
    
    log_message(f"Bot start: {bot_name} di Channel {channel_id}", "SUCCESS")

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

    while True:
        current_time = time.time()
        
        if settings["use_google_ai"]:
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
                log_message(f"Error Loop: {e}", "ERROR")
                time.sleep(5)

        else:
            time.sleep(settings["delay_interval"])
            msg = generate_reply("", settings["prompt_language"], False)
            send_message(channel_id, msg, token,
                         delete_after=settings["delete_bot_reply"],
                         delete_immediately=settings["delete_immediately"])

def get_server_settings(channel_id, channel_name):
    print(f"\n--- PENGATURAN CHANNEL {channel_id} ({channel_name}) ---")
    use_ai = input("Gunakan Gemini AI? (y/n): ").lower() == 'y'
    lang = input("Bahasa (en/id): ").lower()
    if lang not in ['en', 'id']: lang = 'id'

    send_intro = False
    read_delay = 3
    auto_chat = False
    auto_revive = False
    revive_interval = 600
    
    if use_ai:
        send_intro = input("Kirim pesan PEMBUKA (Contextual Intro) saat mulai? (y/n): ").lower() == 'y'
        read_delay = int(input("Interval Cek Pesan (detik) [Default 3]: ") or 3)
        
        print("Mode Auto Chat:")
        print("y = Balas SEMUA chat orang (Rusuh/Nimbrung)")
        print("n = Cuma balas kalau di-REPLY/MENTION (Silent)")
        auto_chat = input("Pilih (y/n): ").lower() == 'y'

        print("\n[FITUR BARU] Auto Revive (Pembangkit Topik):")
        print("Jika chat sepi (tidak ada reply/quote), bot akan bahas topik terakhir lagi.")
        auto_revive = input("Aktifkan Auto Revive? (y/n): ").lower() == 'y'
        if auto_revive:
            revive_interval = int(input("Berapa detik chat harus sepi sebelum bot muncul? (Cth: 600 = 10 menit): ") or 600)

    use_reply = input("Default Reply Mode (Chat biasa reply/tidak)? (y/n): ").lower() == 'y'

    del_after = None
    del_now = False
    if input("Hapus balasan bot? (y/n): ").lower() == 'y':
        del_val = input("Hapus setelah berapa detik? (0/kosong = langsung): ")
        if not del_val or del_val == '0':
            del_now = True
        else:
            del_after = int(del_val)

    return {
        "use_google_ai": use_ai, 
        "prompt_language": lang,
        "send_intro": send_intro,
        "read_delay": read_delay,
        "auto_chat_mode": auto_chat,
        "auto_revive": auto_revive,
        "revive_interval": revive_interval,
        "delay_interval": 60,
        "use_reply": use_reply,
        "delete_bot_reply": del_after, 
        "delete_immediately": del_now
    }

if __name__ == "__main__":
    try:
        ryans.banner()
    except Exception as e:
        print(f"Error loading Ryans Banner: {e}")
        
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
