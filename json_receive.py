import socket
from database import DBSession, Message, User, Chat
from datetime import datetime
from utils import get_text_func
import ijson

TEMP_FILE_NAME = 'history_temp.json'
BUFFER_SIZE = 1024
SEPARATOR = "<SEPARATOR>"

_ = get_text_func()

def decode_utf8(s):
    return s.decode('utf-8', 'ignore')

def strip_user_id(id_):
    id_str = str(id_)
    if id_str.startswith('user'):
        return int(id_str[4:])
    return int(id_str)


def insert_chat_or_do_nothing(chat_id, title):
    session = DBSession()
    target_chat = session.query(Chat).get(chat_id)
    if not target_chat:
        new_chat = Chat(id=chat_id, title=title, enable=False)
        session.add(new_chat)
        session.commit()
    session.close()


def insert_user_or_do_nothing(user_id, fullname, username):
    session = DBSession()
    target_user = session.query(User).get(user_id)
    if not target_user:
        new_user = User(id=user_id, fullname=fullname, username=username)
        session.add(new_user)
        session.commit()
    session.close()

def insert_message(chat_id, message):
    message_id = message.get("id")
    message_type = message.get("type")
    if message_type != "message":
        return 0, 0, None

    message_date = message.get('date')
    message_from = message.get('from', '')
    message_from_id = message.get('from_id', '')
    if message_from_id == "" or not message_from_id.startswith('user'):
        return 0, 0, None

    message_text = message.get('text', '')
    
    insert_user_or_do_nothing(message_from_id[4:], message_from, message_from)
    
    if isinstance(message_text, list):
        msg_text = ""
        for obj in message_text:
            if isinstance(obj, dict):
                msg_text += obj.get('text', '')
            else:
                msg_text += str(obj)
            msg_text += "\n"
    else:
        msg_text = message_text

    if msg_text == '':
        msg_text = _('[other msg]')
    
    message_date = datetime.strptime(message_date, '%Y-%m-%dT%H:%M:%S')
    link_chat_id = str(chat_id)[4:]
    message_from_id = strip_user_id(message_from_id)
    new_msg = Message(id=message_id, 
                      link=f'https://t.me/c/{link_chat_id}/{message_id}', 
                      text=msg_text, 
                      video='', 
                      photo='',
                      audio='', 
                      voice='', 
                      type='text', 
                      category='', 
                      from_id=message_from_id, 
                      from_chat=chat_id, 
                      date=message_date)

    session = DBSession()
    try:
        session.add(new_msg)
        session.commit()
        return 1, 0, None
    except Exception as e:
        print(e)
        return 0, 1, str(message)
    finally:
        session.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 5006))
    server.listen(3)
    while True:
        print("聽取連接中......")
        sock, adddr = server.accept()
        print(_('{}已連接').format(adddr))
        received = sock.recv(BUFFER_SIZE).decode()
        try:
            filename, filesize = received.split(SEPARATOR)
        except ValueError:
            sock.close()
            continue
        filesize = int(filesize)
        receivedsize = 0
        with open(TEMP_FILE_NAME, 'wb') as f:
            while True:
                bytes_read = sock.recv(BUFFER_SIZE)
                f.write(bytes_read)
                receivedsize += BUFFER_SIZE
                if not bytes_read:
                    break
                if receivedsize >= filesize:
                    print(_('文件接收完成 {} {}MB\n').format(
                        filename, round(filesize/1024/1024, 2)))
                    break
        sock.send(_('檢查群組信息...\n').encode())

        # 使用 ijson 流式解析 JSON
        with open(TEMP_FILE_NAME, 'rb') as f:
            parser = ijson.parse(f)
            
            # 獲取群組信息
            group_name = None
            group_id = None
            group_type = ''
            for prefix, event, value in parser:
                if prefix == 'name':
                    group_name = value if isinstance(value, str) else decode_utf8(value)
                elif prefix == 'id':
                    group_id = str(value)
                elif prefix == 'type':
                    group_type = value if isinstance(value, str) else decode_utf8(value)
                if group_name and group_id and group_type:
                    break

        if group_name is None or group_id is None:
            sock.send(_('JSON 讀取錯誤！\n').encode())
            sock.close()
            return

        supergroup_flag = 'supergroup' in group_type
        sock.send(_('checking group info...\n').encode())
        if supergroup_flag != 1:
            sock.send(_('Not supergroup! stopped!\n').encode())
            sock.close()

        sock.send(_('導入中...').encode())
        edited_id = int(group_id) if group_id.startswith('-100') else int('-100' + group_id)
        print(edited_id)
        insert_chat_or_do_nothing(edited_id, group_name)

        success_count, fail_count, fail_messages = 0, 0, []

        # 處理消息
        with open(TEMP_FILE_NAME, 'rb') as f:
            messages = ijson.items(f, 'messages.item', use_float=True, multiple_values=True)
            try:
                for message in messages:
                    # 處理可能的編碼問題
                    for key, value in message.items():
                        if isinstance(value, bytes):
                            message[key] = decode_utf8(value)
                    s, f, m = insert_message(edited_id, message)
                    success_count += s
                    fail_count += f
                    if m:
                        fail_messages.append(m)
            except Exception as e:
                print(e)
        fail_text = ''
        for fail_message in fail_messages:
            fail_text += '{}\n\t'.format(fail_message)
        result_text = _('\n結果\n\t群組: {} ({})\n\t成功: {}\n\t失敗: {}\n\t{}').format(
            group_name, group_id, success_count, fail_count, fail_text)
        sock.sendall(result_text.encode())

        sock.send(_('\n按 Ctrl+C 退出').encode())
        
main()
