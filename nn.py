import time
from telebot import types
import telebot
import sqlite3
import firebase_admin
from firebase_admin import credentials, db, initialize_app
import os

cred = credentials.Certificate("C:\\root\\ksmk\\iqv1-0.json")
firebase_admin.initialize_app(cred, {'databaseURL': 'https://db-mih-default-rtdb.firebaseio.com/'})
database_connections = {
    "اربيل": "erbil.sqlite",
    "الانبار": "anbar.sqlite",
    "بابل": "babl.sqlite",
    "بلد": "balad.sqlite",
    "البصرة": "basra.sqlite",
    "بغداد": "bg.sqlite",
    "دهوك" : "duhok.sqlite",
    "الديوانية-القادسية": "qadisiya.sqlite",
    "كربلاء":"krbl.sqlite",
    "ديالى":"deala.sqlite",
    "ذي قار":"zy.sqlite",
    "السليمانية":"sulaymaniyah.sqlite",
    "صلاح الدين":"salah-aldeen.sqlite",
    "كركوك":"kirkuk.sqlite",
    "المثنى":"muthana.sqlite",
    "ميسان":"mesan.sqlite",
    "النجف":"najaf.sqlite",
    "نينوى":"nineveh.sqlite",
    "واسط":"wasit.sqlite",

}

TOKEN = '6743446171:AAE66jnxWmCE6JWS1BU2HPzqQGp3vNKAVUo'
bot = telebot.TeleBot(TOKEN)
temporary_user_data = {}
temporary_user1_data = {}
user_full_names = {}
user_selected_regions = {}

batch_size = 40
delay_between_batches = 10

retrieved_data = []

# ... (بقية الكود)
def connect_to_database(db_name):
    return sqlite3.connect(db_name)
def create_region_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=2)
    buttons = [types.KeyboardButton(text=region) for region in database_connections.keys()]
    keyboard.add(*buttons)
    return keyboard

OWNER_USER_ID = 6494210314


def is_user_allowed(user_id):
    allowed_users_filename = 'allowed_users.txt'
    if os.path.exists(allowed_users_filename):
        with open(allowed_users_filename, 'r') as file:
            allowed_user_ids = file.read().splitlines()
            return str(user_id) in allowed_user_ids
    return False

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
   # if not is_user_allowed(user_id):
      #  bot.send_message(message.chat.id, "عذرًا، أنت غير مسموح لك باستخدام هذا البوت.")
      #  return

    bot.send_message(message.chat.id, "مرحبًا! قم بإرسال الاسم الثلاثي للبحث عنه.")
    bot.register_next_step_handler(message, get_user_full_name)
    user_data = {"user_id": user_id, "user_name": message.from_user.first_name, "username": message.from_user.username}
    add_user_to_firebase(user_data)

def add_user_to_firebase(user_data):
    try:
        ref = db.reference('/users')  
        ref.child(str(user_data["user_id"])).set(user_data)

    except Exception as e:
        print(f"Error adding user to Firebase: {e}")
def get_user_full_name(message):
    user_full_name = message.text
    user_full_names[message.from_user.id] = user_full_name
    name_parts = user_full_name.split()
    if len(name_parts) != 3:
        bot.send_message(message.chat.id, "الرجاء إدخال اسم ثلاثي فقط اضغط /start من جديد.")
        return
    bot.send_message(message.chat.id, f" الآن، اختر المحافظة للبحث عن الاسم {user_full_name}! :", reply_markup=create_region_keyboard())

@bot.message_handler(func=lambda message: message.text in database_connections.keys())
def handle_selected_region(message):
    user_id = message.from_user.id
    user_full_name = user_full_names.get(user_id, "الصديق")
    selected_region = message.text
    bot.send_message(message.chat.id, f"تم اختيار محافطة {selected_region}! الاسم الذي تود البحث عنه، {user_full_name}.")
    global selected_database_name
    selected_database_name = database_connections.get(selected_region, "")
    name_parts = user_full_names[user_id].split()
    db_name = database_connections.get(selected_region, "") 
    connection = connect_to_database(db_name)

    try:
        cursor = connection.cursor()
        table_name = "person"
        columns = ["p_first", "p_father", "p_grand", "fam_no", "seq_no", "p_birth", "ss_lg_no"]
        query = f"SELECT {', '.join(columns)} FROM {table_name} WHERE p_first LIKE ? AND p_father LIKE ? AND p_grand LIKE ?"
        cursor.execute(query, (f"%{name_parts[0]}%", f"%{name_parts[1]}%", f"%{name_parts[2]}%"))
        results = cursor.fetchall()
        result_batches = [results[i:i + batch_size] for i in range(0, len(results), batch_size)]

        for batch in result_batches:
            for result in batch:
                full_name = " ".join(result[0:3]).strip()  
                birth_date = str(result[5])[:4].lstrip("0") 
                seq_no = str(result[4]).lstrip("0") 
                inline_keyboard = types.InlineKeyboardMarkup()
                show_family_button = types.InlineKeyboardButton("جلب العائلة", callback_data=f"show_family_{result[3]}")
                inline_keyboard.add(show_family_button)

                message_text = f"{full_name}\nالرقم العائلي: {result[3]}\nالتسلسل: {seq_no}\nتاريخ الميلاد: {birth_date}\n\n"
                bot.send_message(message.chat.id, message_text, reply_markup=inline_keyboard)
            time.sleep(delay_between_batches)

    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(message.chat.id, f"Error: {e}")

    finally:
        connection.close()
# تعريف قواميس لتخزين معلومات المستخدم
@bot.callback_query_handler(func=lambda call: call.data.startswith('show_family_'))
def handle_show_family_callback(call):
    fam_no = call.data.split('_')[2]
    user_id = call.from_user.id
    selected_region = user_selected_regions.get(user_id, "")
    db_name = database_connections.get(selected_region, "")
    connection = connect_to_database(selected_database_name)

    try:
        cursor = connection.cursor()
        table_name = "person"
        family_columns = ["p_first", "p_father", "p_grand", "fam_no", "seq_no", "p_birth", "ss_lg_no"]

        # بداية البحث بشكل طبيعي
        family_query = f"SELECT {', '.join(family_columns)} FROM {table_name} WHERE fam_no = ?"
        cursor.execute(family_query, (fam_no,))
        family_results = cursor.fetchall()

        sorted_family_results = sorted(family_results, key=lambda x: x[4])
        
        family_results_text = ""
        target_sequence_found = False

        for person in sorted_family_results:
            family_seq_no = str(person[4]).lstrip("0")
            family_full_name = " ".join(person[0:3]).strip()
            family_birth_date = str(person[5])[:4].lstrip("0")
            birth_year = int(family_birth_date)
            current_year = 2023
            age = current_year - birth_year
            family_results_text += f"الاسم الثلاثي: {family_full_name}\n"
            family_results_text += f"الرقم العائلي: {person[3]}\n"
            family_results_text += f"التسلسل: {family_seq_no}\n"
            family_results_text += f"تاريخ الميلاد: {family_birth_date}\n"
            family_results_text += f"العمر: {age} سنة\n\n"
          #  family_results_text += f"الزقاق: {person[6]}\n\n"

            # إذا كان التسلسل يساوي 1 أو 2، قم بحفظ المعلومات
            if family_seq_no == "1":
             print("Saving Information for Sequence:", family_seq_no)
             user_id = call.from_user.id
             user_data = {
                "user_id": user_id,
                "p_father": person[1],
                "p_grand": person[2],
                "ss_lg_no": person[6],
                "seq_no": person[4],
             }
             temporary_user_data[user_id].append(user_data)

             #temporary_user_data.append(user_data)
            print(temporary_user_data)
            if family_seq_no == "2":
             print("Saving Information for Sequence:", family_seq_no)
             user_id = call.from_user.id
             user_data = {
                "user_id": user_id,
                "p_father": person[1],
                "p_grand": person[2],
                "ss_lg_no": person[6],
                "seq_no": person[4],
             }
             temporary_user1_data[user_id].append(user_data)

             #temporary_user1_data.append(user_data)
            print(temporary_user1_data)
        bot.send_message(call.message.chat.id, family_results_text)

        

    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(call.message.chat.id, f"Error: {e}")

    finally:
        connection.close()

@bot.message_handler(commands=['get'])
def handle_get_command(message):
    user_id = message.from_user.id
    reply_keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    show_sequence1_button = types.KeyboardButton("اضهار العمام")
    show_sequence2_button = types.KeyboardButton("اضهار الخوال")
    reply_keyboard.add(show_sequence1_button, show_sequence2_button)

    bot.send_message(user_id, "اختر ما تريد عرضه:", reply_markup=reply_keyboard)
    user_selected_regions[user_id] = "get"
@bot.message_handler(func=lambda message: message.text in ["اضهار العمام", "اضهار الخوال"])
def handle_show_data_choice(message):
    user_id = message.from_user.id
    selected_option = message.text

    # Reset user data dictionaries before displaying new results
    temporary_user_data[user_id] = {}
    temporary_user1_data[user_id] = {}

    if selected_option == "اضهار العمام":
        bot.send_message(user_id, "جاري عرض معلومات العمام...")
        show_user_data(user_id, temporary_user_data)
    elif selected_option == "اضهار الخوال":
        bot.send_message(user_id, "جاري عرض معلومات الخوال...")
        show_user_data(user_id, temporary_user1_data)
    else:
        bot.send_message(user_id, "خيار غير صالح. يرجى اختيار 'اضهار العمام' أو 'اضهار الخوال'.")

def show_user_data(user_id, user_data_list):
    result_message = "النتائج:\n"
    for user_data in user_data_list:
        p_father = user_data.get("p_father", "")
        p_grand = user_data.get("p_grand", "")
        ss_lg_no = user_data.get("ss_lg_no", "")
        search_result = search_user_in_database(selected_database_name, p_father, p_grand, ss_lg_no)
        result_message += f"{search_result}\n"
    bot.send_message(user_id, result_message)

def search_user_in_database(db_name, p_father, p_grand, ss_lg_no):
    connection = connect_to_database(db_name)
    try:
        cursor = connection.cursor()
        table_name = "person"
        columns = ["p_first", "p_father", "p_grand", "fam_no", "seq_no", "p_birth", "ss_lg_no"]
        query = f"SELECT {', '.join(columns)} FROM {table_name} WHERE p_father=? AND p_grand=? AND ss_lg_no=?"
        cursor.execute(query, (p_father, p_grand, ss_lg_no))
        results = cursor.fetchall()
        formatted_results = []
        for result in results:
            full_name = " ".join(result[0:3]).strip()
            fam_no = result[3]
            seq_no = str(result[4]).lstrip("0")
            birth_date = str(result[5])[:4].lstrip("0")
            current_year = 2023
            age = current_year - int(birth_date)
            ss_lg_no = result[6]
            
            result_text = (
                f"الاسم الثلاثي: {full_name}\n"
                f"الرقم العائلي: {fam_no}\n"
                f"التسلسل: {seq_no}\n"
                f"تاريخ الميلاد: {birth_date}\n"
                f"العمر: {age} سنة\n"
             #   f"الزقاق: {ss_lg_no}\n\n"
            )
            formatted_results.append(result_text)

        return "\n".join(formatted_results)
    except Exception as e:
        print(f"Error searching in database: {e}")
        return "خطأ في البحث في قاعدة البيانات"
    finally:
        connection.close()

if __name__ == "__main__":
    bot.polling(none_stop=True)
