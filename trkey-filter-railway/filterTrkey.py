# -*- coding: utf-8 -*-
from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import EditBannedRequest, GetParticipantRequest, GetFullChannelRequest
from telethon.tl.types import ChatBannedRights, ChannelParticipantSelf
from telethon.tl.functions.messages import ImportChatInviteRequest
try:
    from telethon.errors import FloodWait    # Telethon ≥ 1.34
except ImportError:
    from telethon.errors.rpcerrorlist import FloodWaitError as FloodWait
import asyncio, time

# ============== بيانات الدخول والإعدادات ==============
# الـ API ID والـ API Hash الخاصين بحسابك الشخصي (Userbot)
# **تأكد أن هذه القيم صحيحة من my.telegram.org**
api_id = 23873818
api_hash = '0fb82e50665a5406979304c7fce10a6f'

# توكن البوت اللي أنت عاوزه يشتغل كواجهة (من @BotFather)
# ******** يجب عليك تغيير هذا التوكن بالتوكن الصحيح الخاص بك من BotFather ********
BOT_TOKEN = '7719445927:AAGv46a1rmtuDGYGrWT2rx8_gilYQsXU31I' # تأكد أن هذا التوكن هو بتاعك

# معلومات المطور والقناة (للاستخدام في الخاص فقط)
DEV_USERNAME = "developer: @XCODE000"  
CHANNEL_LINK_DISPLAY_TEXT = "TiTo" # النص اللي هيظهر للينك
CHANNEL_LINK_URL = "https://t.me/l_zor_l"

# إنشاء الكلاينت: سيعمل كـ Userbot (بصلاحيات حسابك) وسيستقبل الأوامر كبوت (بالتوكن)
cli = TelegramClient("tito_session", api_id, api_hash).start(bot_token=BOT_TOKEN)

# إعدادات الحظر
BAN_RIGHTS = ChatBannedRights(until_date=None, view_messages=True) # حظر دائم

# مجموعات تم إيقاف التطهير فيها
STOP_CLEANUP = set()
# قاموس لتخزين مهام التطهير النشطة لكل دردشة
ACTIVE_CLEANUPS = {}
# قاموس لتخزين روابط الدعوة لكل شات
CHAT_INVITE_LINKS = {}

# قاموس لتخزين رسائل البدء المؤقتة ليتم حذفها لاحقًا
START_MESSAGES_TO_DELETE = {}

# --- وظائف مساعدة ---

# حظر مستخدم مع تجاوز FloodWait والأخطاء الشائعة
async def ban_user(chat_id, user_id):
    while True:
        try:
            await cli(EditBannedRequest(chat_id, user_id, BAN_RIGHTS))
            # print(f"Successfully banned user {user_id} in {chat_id}.") # إزالة طباعة النجاح لتقليل الحمل
            return True
        except FloodWait as e:
            print(f"FloodWait: Waiting for {e.seconds} seconds before retrying ban for {user_id} in {chat_id}")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            error_str = str(e).lower()
            if "user_admin_invalid" in error_str or "not an admin" in error_str or "participant is not a member" in error_str or "user_not_participant" in error_str:
                # هذا اليوزر ليس موجودا او ادمن او غير مشارك
                # print(f"Skipping ban for {user_id} in {chat_id}: User is an admin, not a member, or cannot be banned by bot. Error: {e}") # إزالة طباعة التخطي
                return False
            elif "channelprivateerror" in error_str or "chat_write_forbidden" in error_str or "peer_id_invalid" in error_str:
                print(f"Bot lost access to chat {chat_id}. Attempting to re-join. Error: {e}")
                STOP_CLEANUP.add(chat_id) # أوقف العملية
                await re_join_chat(chat_id) # حاول إعادة الانضمام
                return False
            else:
                # print(f"Failed to ban user {user_id} in {chat_id} due to unhandled error: {e}") # إزالة طباعة الخطأ العام
                return False

# العامل المسؤول عن تنفيذ الحظر من قائمة الانتظار
async def worker(chat_id, queue, counter_list):
    me_id = (await cli.get_me()).id # جلب ID البوت مرة واحدة
    while True:
        user = await queue.get()
        if user is None: # قيمة حراسة للإشارة إلى العامل بالتوقف
            queue.task_done()
            break
        
        if chat_id in STOP_CLEANUP:
            queue.task_done()
            continue
        
        # تحسين التحقق: محاولة الحظر مباشرة ثم التعامل مع الأخطاء
        # هذا يقلل من عدد طلبات GetParticipantRequest التي قد تكون بطيئة
        if user.id == me_id or user.bot: # لا تحظر البوت نفسه أو البوتات الأخرى
            queue.task_done()
            continue

        # محاولة الحظر وإضافة العداد لو نجح
        ban_successful = await ban_user(chat_id, user.id)
        if ban_successful:
            counter_list[0] += 1 # زيادة العداد فقط عند النجاح
        
        queue.task_done() # اكمال مهمة المستخدم بغض النظر عن نجاح الحظر

# دالة لإعادة الانضمام للمحادثة (صامتة في المجموعة)
async def re_join_chat(chat_id):
    if chat_id in CHAT_INVITE_LINKS and CHAT_INVITE_LINKS[chat_id]:
        invite_hash = CHAT_INVITE_LINKS[chat_id].split('/')[-1]
        print(f"Attempting to re-join chat {chat_id} using invite link: {CHAT_INVITE_LINKS[chat_id]}")
        try:
            await cli(ImportChatInviteRequest(invite_hash))
            print(f"Successfully re-joined chat {chat_id}.")
            STOP_CLEANUP.discard(chat_id) # أزل من قائمة الإيقاف لتسمح بالاستئناف لو لسه فيه شغل
            return True
        except Exception as e:
            print(f"Failed to re-join chat {chat_id}: {e}")
            return False
    else:
        print(f"No invite link available for chat {chat_id}. Cannot re-join automatically.")
        return False

# مهمة التنظيف السريعة جداً (التصفية الخاطفة الشبحية)
async def blitz_cleanup(chat_id):
    queue = asyncio.Queue()
    counter_list = [0]
    users_to_ban = []    

    print(f"Starting blitz cleanup for {chat_id}: Gathering all participants first...")
    start_gather_time = time.time()

    # محاولة الحصول على رابط الدعوة (صامتة تماماً للمستخدم)
    # هذه الخطوة مهمة جداً لضمان قدرة البوت على العودة إذا طُرد
    if chat_id not in CHAT_INVITE_LINKS or not CHAT_INVITE_LINKS[chat_id]:
        try:
            full_chat = await cli(GetFullChannelRequest(chat_id))
            if full_chat.full_chat.exported_invite:
                CHAT_INVITE_LINKS[chat_id] = full_chat.full_chat.exported_invite.link
                print(f"Obtained invite link for {chat_id}: {CHAT_INVITE_LINKS[chat_id]}")
            else:
                print(f"No invite link available for {chat_id}. Automatic re-join might fail.")
        except Exception as e:
            print(f"Could not get invite link for {chat_id}: {e} (suppressed message for user)")
            pass    

    try:
        # استخدام aggressive=True لجمع أكبر عدد ممكن من المشاركين بسرعة
        # لا نقوم بالتحقق من الأدمان هنا لتقليل الحمل، سيتم التعامل معها في العامل
        async for user in cli.iter_participants(chat_id, aggressive=True):
            users_to_ban.append(user)

        print(f"Finished gathering {len(users_to_ban)} potential users to ban in {int(time.time()-start_gather_time)} seconds.")

    except Exception as e:
        print(f"Error during initial participant gathering for chat {chat_id}: {e}")
        error_str = str(e).lower()
        if "channelprivateerror" in error_str or "chat_write_forbidden" in error_str or "peer_id_invalid" in error_str:
            print(f"Bot lost access to chat {chat_id} during gather. Attempting to re-join and stopping cleanup.")
            STOP_CLEANUP.add(chat_id)
            await re_join_chat(chat_id) # حاول يرجع بس بصمت
            return    

    # بدء العمال بعد جمع كل المستخدمين
    # زيادة عدد العمال بشكل كبير جداً لتحقيق أقصى سرعة
    NUM_WORKERS = 100 # تم زيادة العدد هنا
    workers_tasks = [asyncio.create_task(worker(chat_id, queue, counter_list)) for _ in range(NUM_WORKERS)]

    # إضافة كل المستخدمين للـ queue
    for user in users_to_ban:
        if chat_id in STOP_CLEANUP:
            break
        await queue.put(user)
    
    # إرسال قيم الحراسة للعمال ليتوقفوا بعد إفراغ الـ queue
    for _ in workers_tasks:
        await queue.put(None)    

    print(f"All {len(users_to_ban)} users added to queue. Waiting for workers to finish...")
    start_ban_time = time.time()

    # انتظار العمال لإنهاء مهامهم
    await queue.join()
    await asyncio.gather(*workers_tasks)

    print(f"Blitz cleanup for chat {chat_id} finished. Total banned: {counter_list[0]} in {int(time.time()-start_ban_time)} seconds for banning phase.")
    
    # حذف مهمة التنظيف من القائمة النشطة
    if chat_id in ACTIVE_CLEANUPS:
        del ACTIVE_CLEANUPS[chat_id]
    
    # ***** الرسالة الجديدة بعد انتهاء التصفية *****
    try:
        if not chat_id in STOP_CLEANUP: # تأكد أن التصفية لم تتوقف يدويًا
            await cli.send_message(chat_id, "علشان تبقي تحك يا كسمك في عمك تيتو🩴")
    except Exception as e:
        print(f"Failed to send completion message in {chat_id}: {e}")
        pass

# --- أوامر البوت (صامتة في المجموعة قدر الإمكان) ---

# رسالة الترحيب /start (فقط في الخاص)
@cli.on(events.NewMessage(pattern='/start'))
async def start_command(event):
    if event.is_private:
        me = await event.client.get_me()
        await event.respond(
            f"""✨ مرحباً بك في عالم تيتو! ✨

أنا هنا لأجعل مجموعتك أكثر نظاماً ونظافة.
أقوم بتصفية الأعضاء غير المرغوب فيهم بسرعة وكفاءة عالية.

🔥 *كيف أبدأ العمل؟*
فقط أرسل كلمة «تيتو» في المجموعة وسأبدأ مهمتي فوراً.

🛑 *لإيقاف التصفية:* أرسل كلمة «بس» في المجموعة.

{DEV_USERNAME}
📢 **chanal:** [{CHANNEL_LINK_DISPLAY_TEXT}]({CHANNEL_LINK_URL})""",
            buttons=[
                [Button.inline("🛠 الأوامر", b"commands")],
                [Button.url("📢 انضم للقناة", CHANNEL_LINK_URL)],
                [Button.url("➕ أضفني لمجموعتك", f"https://t.me/{me.username}?startgroup=true")]
            ]
        )
    elif event.is_group:
        # لا يرد على /start في المجموعات على الإطلاق
        pass

# زر الأوامر والرجوع (فقط في الخاص)
@cli.on(events.CallbackQuery(data=b"commands"))
async def command_help_callback(event):
    await event.answer()
    await event.edit(
        """🧠 *طريقة التشغيل:*

- أرسل كلمة `تيتو` في أي مجموعة وأنا مشرف فيها وسأبدأ التصفية فوراً.
- أرسل `بس` لإيقاف التصفية.

📌 *ملاحظة هامة:* تأكد أن البوت لديه صلاحيات المشرف الكاملة و'حظر المستخدمين' و'حذف الرسائل' ليعمل بكفاءة.""",
        buttons=[Button.inline("🔙 رجوع", b"back_to_start")]
    )

@cli.on(events.CallbackQuery(data=b"back_to_start"))
async def back_to_start_callback(event):
    await event.answer()
    me = await event.client.get_me()
    await event.edit(
        f"""✨ مرحباً بك في عالم تيتو! ✨

أنا هنا لأجعل مجموعتك أكثر نظاماً ونظافة.
أقوم بتصفية الأعضاء غير المرغوب فيهم بسرعة وكفاءة عالية.

🔥 *كيف أبدأ العمل؟*
فقط أرسل كلمة «تيتو» في المجموعة وسأبدأ مهمتي فوراً.

🛑 *لإيقاف التصفية:* أرسل كلمة «بس» في المجموعة.

{DEV_USERNAME}
📢 **chanal:** [{CHANNEL_LINK_DISPLAY_TEXT}]({CHANNEL_LINK_URL})""",
            buttons=[
                [Button.inline("🛠 الأوامر", b"commands")],
                [Button.url("📢 انضم للقناة", CHANNEL_LINK_URL)],
                [Button.url("➕ أضفني لمجموعتك", f"https://t.me/{me.username}?startgroup=true")]
            ]
    )

# أمر "تيتو" لبدء التصفية (الرد الوحيد في المجموعة و سيتم حذفه فوراً)
@cli.on(events.NewMessage(pattern='(?i)تيتو', chats=None))
async def start_cleanup_command(event):
    if not event.is_group and not event.is_channel:
        return    

    chat_id = event.chat_id
    me = await cli.get_me()

    try:
        participant_me = await cli(GetParticipantRequest(chat_id, me.id))
        
        # تحقق من صلاحية حظر المستخدمين (Ban users)
        # تم تحسين هذا الجزء ليكون أكثر أماناً في الوصول لـ admin_rights
        has_admin_rights_obj = getattr(participant_me.participant, "admin_rights", None)

        has_ban_permission = has_admin_rights_obj and getattr(has_admin_rights_obj, "ban_users", False)
        
        # تحقق من صلاحية حذف الرسائل (Delete messages)
        has_delete_permission = has_admin_rights_obj and getattr(has_admin_rights_obj, "delete_messages", False)
        
        # تحقق من صلاحية دعوة المستخدمين (Invite users)
        has_invite_permission = has_admin_rights_obj and getattr(has_admin_rights_obj, "invite_users", False)
        
        if not has_ban_permission:
            print(f"Bot in chat {chat_id} lacks 'ban_users' permission. Cannot proceed.")
            # لا يرد على المستخدم في المجموعة بهذا الخطأ، فقط في الـ Terminal
            return
        
        if not has_delete_permission:
            print(f"Bot in chat {chat_id} lacks 'delete_messages' permission. Ghost mode might fail.")
            # لا يرد على المستخدم في المجموعة بهذا الخطأ
            # لا توقف العملية، فقط سجل التحذير
            pass 
            
        if not has_invite_permission:
            print(f"Bot does not have 'invite users via link' permission in {chat_id}. Automatic re-join might fail.")
            pass # لا توقف العملية، فقط سجل التحذير
        
        try:
            full_chat = await cli(GetFullChannelRequest(chat_id))
            if full_chat.full_chat.exported_invite:
                CHAT_INVITE_LINKS[chat_id] = full_chat.full_chat.exported_invite.link
                print(f"Initial invite link for {chat_id}: {CHAT_INVITE_LINKS[chat_id]}")
            else:
                print(f"No invite link available for {chat_id}. Automatic re-join might fail.")
                pass
        except Exception as ex:
            print(f"Could not get initial invite link for {chat_id}: {ex} (suppressed message for user)")
            pass

    except Exception as err:
        print(f"Error checking bot permissions in chat {chat_id}: {err}")
        # لا يرد على المستخدم في المجموعة بأي خطأ في الصلاحيات
        return


    if chat_id in ACTIVE_CLEANUPS and not ACTIVE_CLEANUPS[chat_id].done():
        print(f"Cleanup already running in chat {chat_id}.")
        # لا يرد على المستخدم في المجموعة
        return

    STOP_CLEANUP.discard(chat_id)

    # إرسال الرسالة الأولية وحفظها لحذفها فوراً
    initial_message = await event.reply("😈🩴 **جارِ تصفية المجموعة...**") # تم تغيير النص الأولي ليكون أكثر حيادية
    START_MESSAGES_TO_DELETE[chat_id] = initial_message

    # جدولة حذف الرسالة فوراً (بعد جزء صغير جداً من الثانية)
    await asyncio.sleep(0.5) # نصف ثانية فقط
    try:
        if chat_id in START_MESSAGES_TO_DELETE:
            await START_MESSAGES_TO_DELETE[chat_id].delete()
            del START_MESSAGES_TO_DELETE[chat_id]
    except Exception as e:
        print(f"Failed to delete initial message in {chat_id}: {e}")
        pass # تجاهل الخطأ لو مقدرش يحذف الرسالة (مثل لو البوت اطرد بسرعة فائقة)

    # تشغيل عملية التصفية الخاطفة في الخلفية
    cleanup_task = asyncio.create_task(blitz_cleanup(chat_id))
    ACTIVE_CLEANUPS[chat_id] = cleanup_task


# أمر "بس" لإيقاف التصفية (صامت تماماً في المجموعة)
@cli.on(events.NewMessage(pattern='(?i)بس', chats=None))
async def stop_cleanup_command(event):
    if not event.is_group and not event.is_channel:
        pass # لا يرد على "بس" في الخاص

    chat_id = event.chat_id
    
    STOP_CLEANUP.add(chat_id)

    if chat_id in ACTIVE_CLEANUPS:
        await asyncio.sleep(0.5) # إعطاء فرصة لـ blitz_cleanup لتلاحظ التوقف
        if ACTIVE_CLEANUPS[chat_id].done():
            del ACTIVE_CLEANUPS[chat_id]
            print(f"Cleanup in chat {chat_id} stopped.")
        else:
            try:
                # محاولة إلغاء المهمة إذا كانت لا تزال قيد التشغيل
                ACTIVE_CLEANUPS[chat_id].cancel()
                await ACTIVE_CLEANUPS[chat_id] # انتظر حتى يتم إلغاؤها
                del ACTIVE_CLEANUPS[chat_id]
                print(f"Cleanup in chat {chat_id} stopped and task cancelled.")
            except asyncio.CancelledError:
                print(f"Cleanup task for {chat_id} was successfully cancelled.")
                del ACTIVE_CLEANUPS[chat_id]
            except Exception as e:
                print(f"Error stopping cleanup task for {chat_id}: {e}")
                pass # لا يرد على المستخدم
    else:
        print(f"No cleanup running in chat {chat_id} to stop.")
    pass # لا يرسل أي رسالة للمستخدم


# عند انضمام عضو جديد (صامت تماماً في المجموعة)
@cli.on(events.ChatAction)
async def new_members_action(event):
    # ************** تم تعديل هذا الجزء لتحسين التعامل مع الأخطاء **************
    # التأكد أن event.user ليس None قبل الوصول لـ .id
    # والتعامل مع أنواع الكائنات المختلفة مثل ChannelParticipantSelf
    if event.user_added and event.user and event.user.id == (await cli.get_me()).id:
        print(f"Userbot was added to chat {event.chat_id}. Checking permissions...")
        try:
            chat_id = event.chat_id
            me = await cli.get_me()
            # التأكد من الحصول على كائن Participant صحيح
            participant_me = await cli(GetParticipantRequest(chat_id, me.id))
            
            # التحقق من وجود صلاحيات الإدارة قبل الوصول إليها
            has_admin_rights_obj = getattr(participant_me.participant, "admin_rights", None)
            
            has_ban_permission = has_admin_rights_obj and getattr(has_admin_rights_obj, "ban_users", False)
            has_delete_permission = has_admin_rights_obj and getattr(has_admin_rights_obj, "delete_messages", False)
            has_invite_permission = has_admin_rights_obj and getattr(has_admin_rights_obj, "invite_users", False)

            if not has_ban_permission:
                print(f"Bot added to chat {chat_id} but lacks 'ban_users' permission. Cannot perform cleanup.")
            elif not has_delete_permission:
                print(f"Bot added to chat {chat_id} but lacks 'delete_messages' permission. Ghost mode might fail.")
            elif not has_invite_permission:
                print(f"Bot added to chat {chat_id} but lacks 'invite_users' permission. Automatic re-join might fail.")
            else:
                print(f"Bot added to chat {chat_id} successfully and has all required permissions for ghost mode.")
        except Exception as e:
            print(f"Error checking permissions after addition to chat {event.chat_id}: {e}")
            pass
    elif event.user_added: # لمعالجة أي حالات أخرى لـ user_added (مثل رسائل الخدمة أو إذا كان event.user=None)
        print(f"User added event detected for chat {event.chat_id}, but specific user ID could not be determined or was a service message. Skipping detailed permission check.")
        pass

# ***** دالة جديدة لحذف رسائل السبام *****
@cli.on(events.NewMessage(chats=None)) # استمع لجميع الرسائل في جميع الدردشات
async def delete_spam_messages(event):
    if not event.is_group and not event.is_channel:
        return # لا تعمل في الخاص

    # تأكد أن البوت لديه صلاحيات حذف الرسائل
    try:
        me = await cli.get_me()
        participant_me = await cli(GetParticipantRequest(event.chat_id, me.id))
        has_delete_permission = getattr(participant_me.participant, "admin_rights", None) and \
                                getattr(participant_me.participant.admin_rights, "delete_messages", False)
        if not has_delete_permission:
            # إذا لم يكن لديه صلاحية حذف، اطبع تحذيرًا وتوقف
            # print(f"Bot in chat {event.chat_id} lacks 'delete_messages' permission for anti-spam. Skipping.")
            return
    except Exception as e:
        # لو حدث خطأ في جلب الصلاحيات، لا يمكننا الحذف
        # print(f"Error checking delete permissions for anti-spam in {event.chat_id}: {e}")
        return

    message_text = event.raw_text.lower() if event.raw_text else ""
    
    # قائمة بالكلمات المفتاحية والروابط التي تشير إلى الرسالة التي تريد حذفها
    spam_keywords = [
        "freeether.net",
        "claim free ethereum",
        "free eth alert",
        "airdrop won't last forever",
        "connect your wallet, verify",
        "no registration. instant rewards",
        "free money slip away",
        "www.freeether.net" # للتأكيد على الرابط
    ]

    # التحقق مما إذا كانت الرسالة تحتوي على أي من الكلمات المفتاحية
    is_spam = False
    for keyword in spam_keywords:
        if keyword in message_text:
            is_spam = True
            break
            
    # يمكنك أيضاً التحقق من وجود صور معينة إذا كانت الرسالة دائمًا مصحوبة بصورة محددة
    # if event.photo:
    #     # هنا يمكنك إضافة منطق للتحقق من Photo ID أو خصائص أخرى للصورة
    #     # هذا يتطلب جمع معرفات الصور المشبوهة أولاً
    #     # مثال: if event.photo.id == SOME_KNOWN_SPAM_PHOTO_ID:
    #     #     is_spam = True

    if is_spam:
        try:
            await event.delete()
            # ************** تم التعديل هنا: طباعة رسالة عامة بدلاً من محتوى الرسالة **************
            print(f"Spam message detected and deleted from chat {event.chat_id}.")
            # يمكنك اختيار حظر المستخدم أيضاً إذا كنت ترغب في ذلك
            # await ban_user(event.chat_id, event.sender_id)
            # print(f"Banned user {event.sender_id} for sending spam in chat {event.chat_id}")
        except Exception as e:
            print(f"Failed to delete spam message in {event.chat_id}: {e}")
            pass # تجاهل الخطأ لو مقدرش يحذف الرسالة

print("🔥 تيتو - بوت التصفية الفاجر يعمل الآن!")
print(f"البوت يعمل بالتوكن: {BOT_TOKEN}")
print(f"الحساب يعمل بالـ API ID: {api_id}")

cli.run_until_disconnected()
