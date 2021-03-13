import weechat
import subprocess
import json
import socket
import tempfile
import collections
import time

# =================================[ Callback functions ]================================== {{{

def private_input_cb(data, buffer, input_data):
    ## I need to echo out the data
    global status
    api = {"method": "send", "params": {"options": {"conversation_id": data, "message": {"body": input_data}}}}
    #echo = status.nick_name+'\t'+input_data
    #weechat.prnt_date_tags(buffer, 0, "", echo) 
    # And then, i need to send it
    r=status.execute_api(api)
    ## CHECK r. Moreover, we can trigger the execution in another thread
    return weechat.WEECHAT_RC_OK

def away_command_cb(data, current_buffer, args):
    global status
    if (status.is_away == True):
        weechat.prnt("", "Weebase is awake")
        status.is_away = False
    else:
        weechat.prnt("", "Weebase is sleeping")
        status.is_away = True
    return weechat.WEECHAT_RC_OK_EAT

def private_close_cb(data, buffer):
    global status
    del status.private_chans[data]
    return weechat.WEECHAT_RC_OK

## Todo wrapper 
def status_input_cb(data, buffer, input_data):
    weechat.prnt("", str(data) + str(input_data))
    return weechat.WEECHAT_RC_OK

def status_close_cb(data, buffer):
    weechat.prnt("", str(data))
    return weechat.WEECHAT_RC_OK

def start_reading(data, command, return_code, out, err):
    #weechat.prnt("","Command:"+str(command))
    ## Maybe we can check this to see if the program is crashed
    #weechat.prnt("","return_code:"+str(return_code))
    global status

    weechat.prnt("","out:"+str(out))
    if out == "":
        return weechat.WEECHAT_RC_OK
    j = json.loads(out)
    if j['type'] != 'chat':
        weechat.prnt_date_tags("", "","", str(j))
    id = j['msg']['conversation_id']
    date,body,n = handle_message(j['msg'], status.nick_name)

    # Mark messages read only if weechat are not set _away_
    if (status.is_away == False):
        mark_message_read(id, j['msg']['id'])

    if id not in status.private_chans:
        status.open_conv_id(j['msg'])

    # Default Priority is notify_private
    priority = "notify_private"

    # Use self_message in case it's our own message
    if (j['msg']['sender']['username'] == status.nick_name):
            priority = "self_message"

    # History reading
    if weechat.buffer_get_string(status.private_chans[id], "localvar_first_message") == "":
        r, f, l = status.get_last_history(id)
        weechat.buffer_set(status.private_chans[id], "localvar_set_first_message", str(f))
        weechat.buffer_set(status.private_chans[id], "localvar_set_last_message", str(l))

    # Print new message
    weechat.prnt_date_tags(status.private_chans[id], date, priority, body)

    # if debug:
    #     body = weechat.color('/darkgray')+"DEBUG\t"+weechat.color('/darkgray')+str(j)
    #     weechat.prnt_date_tags(status.private_chans[id], date,"notify_none", body)
    #notify_none Buffer with line is not added to hotlist.
    #notify_message Buffer with line is added to hotlist with level "message".
    #notify_private Buffer with line is added to hotlist with level "private".
    #notify_highlight Buffer with line is added to hotlist with level "highlight". 
    #weechat.prnt("","err:"+str(err))
    return weechat.WEECHAT_RC_OK

def handle_system_message(msg):
    system = msg['content']['system']
    body = weechat.color("/cyan")+"SYSTEM\t"
    if system['systemType'] == 0:
        ## someone added someone to chat
        addedtoteam = system['addedtoteam']
        adder = addedtoteam['adder']
        addee = addedtoteam['addee']
        role  = addedtoteam['role']
        bulkAdds = addedtoteam['bulkAdds']
        body = weechat.color("/cyan")+adder+" added \'"+addee+"\' to team with role "+str(role)
    elif system['systemType'] == 3:
        # Creation of new team
        team_name = system['createteam']['team']
        creator   = system['createteam']['creator']
        body += weechat.color("/cyan")+creator+" created \'"+team_name+"\' team"
    elif system['systemType'] == 7:
        # Bulk add
        bulkaddtoconv = system['bulkaddtoconv']
        username = bulkaddtoconv['usernames']
        users = (",").join(username[:])
        body = weechat.prefix("join") +users+ " have joined the channel" 
    elif system['systemType'] == 9:
        ## Creation of a new channel
        new_channel = system['newchannel']
        creator = new_channel['creator']
        name_channel = new_channel['nameAtCreation']
        body+=weechat.color("/cyan")+creator+" created \'"+name_channel+"\' channel"
    else:
        body+=weechat.color("red")+"type not supported. Raw message:"+str(msg)
    return body

def add_reaction(msg, buffer):
    #hdata = weechat.hdata_get("b
    pass

#{"method": "mark", "params": {"options": {"channel": {"name": "you,them"}, "message_id": 72}}} mark the message read.. we can use when we switch buffer
# If it from history we can skip the delete and modify messages
def handle_message(msg, user_nick_name, is_history=False):
    sender = msg['sender']['username']
    date = msg['sent_at']
    content = msg['content']['type']
    id = msg['id']
    #global status
    if sender == user_nick_name:
        sender = weechat.color("lightgreen") + sender
    sender = sender+weechat.color("/lightmagenta")+" ["+str(id)+"]"
    if content == 'join':
        body = weechat.prefix("join")+sender+" has joined the channel"
    elif content == 'system':
        body = handle_system_message(msg)
    elif content == 'text':
        text = msg['content']['text']

        re_header = ""
        if "replyTo" in text.keys():
            re_header = weechat.color("*lightcyan") + "RE[" + str(text["replyTo"]) +"]: " + weechat.color("reset")

        msg_body = re_header + text['body'].replace('\t',"    ")

        ## Mention username
        user_mention =  text['userMentions']
        if user_mention != None:
            for user in user_mention:
                msg_body = msg_body.replace('@'+user['text'],weechat.color("*red")+'@'+user['text']+weechat.color("reset"))
                #if user['text'] == self.nick --> PRIORITY

        body = sender+'\t'+msg_body
    #elif content == 'unfurl':
    #    body = sender+'\t'+
    elif content == 'reaction':
        reaction = msg['content']['reaction']['b']
        message_id = msg['content']['reaction']['m']
        body = sender+'\t'+weechat.color("*lightmagenta") + reaction + " for [" + str(message_id) + "]"
    elif content == 'delete':
        body = sender+'\t'+weechat.color("*red")+"DELETE: "+str(msg['content']['delete']['messageIDs'])
    elif content == 'edit':
        edit = msg['content']['edit']
        body = sender+'\t'+weechat.color("*red")+"EDIT: "+str(edit['messageID'])+" with: \'"+edit['body']+"\'"
    elif content == 'metadata':
        body = sender+'\t'+"Metadata: Conversation Title: "+msg['content']['metadata']['conversationTitle']
    elif content == 'headline':
        headline = msg['content']['headline']['headline']
        body = sender + '\t' + weechat.color("*lightmagenta") + "HEADLINE: " + headline
    elif content == 'attachment':
        filename = msg['content']['attachment']['object']['filename']
        mimetype = msg['content']['attachment']['object']['mimeType']
        title = msg['content']['attachment']['object']['title']
        size = msg['content']['attachment']['object']['size']
        body = sender+"\t"+weechat.color("*green")+"FILE: " + title + " <"+filename+"> ("+ mimetype +" "+ str(size) +" B)  "+weechat.color("*magenta")+" /download "+str(id)+" <output>"
    #elif content == 'pin':
    #    body = sender+'\t'+weechat.color("_lightgreen")+"has pinned message "+str(id)
    else:
        body = weechat.color("*red")+str(msg)

    #mark message
    return date,body,msg['id']

def reply_message_buffer(data, buffer, arg):
    args = arg.split(' ')
    if len(args) < 2:
        return weechat.WEECHAT_RC_ERROR
    conv_id = weechat.buffer_get_string(buffer, "localvar_conversation_id")
    api = {"method": "send", "params": {"options": {"conversation_id": conv_id, "message": {"body": " ".join(args[1:])}, "reply_to": int(args[0])}}}
    r=status.execute_api(api)
    return weechat.WEECHAT_RC_OK

def delete_message_buffer(data, buffer, arg):
    args = arg.split(' ')
    if len(args) != 1:
        return weechat.WEECHAT_RC_ERROR
    conv_id = weechat.buffer_get_string(buffer, "localvar_conversation_id")
    api = {"method": "delete", "params": {"options": {"conversation_id": conv_id, "message_id": int(args[0])}}}
    r=status.execute_api(api)
    return weechat.WEECHAT_RC_OK

def attach_file(data, buffer, arg):
    args = arg.split(' ')
    if len(args) < 1:
        return weechat.WEECHAT_RC_ERROR
    elif len(args) > 1:
        title = " ".join(args[1:])
    else:
        title = args[0]
    conv_id = weechat.buffer_get_string(buffer, "localvar_conversation_id")
    api = {"method": "attach", "params": {"options": {"conversation_id": conv_id, "filename": args[0], "title": title}}}
    ## CHECK r
    r=status.execute_api(api)
    return weechat.WEECHAT_RC_OK

def open_attachment(data, buffer, arg):
    if arg == "":
        return weechat.WEECHAT_RC_ERROR
    conv_id = weechat.buffer_get_string(buffer, "localvar_conversation_id")
    tmp_file = tempfile.mkstemp(suffix = '.ktmp')
    weechat.prnt("", str(tmp_file))
    api = {"method": "download", "params": {"options": {"conversation_id": conv_id, "message_id": int(arg), "output": tmp_file[1]}}}
    ## CHECK r
    r=status.execute_api(api)
    subprocess.Popen(['xdg-open',tmp_file[1]],close_fds=True)
    return weechat.WEECHAT_RC_OK

def download_message(data, buffer, arg):
    args = arg.split(' ')
    if len(args) != 2:
        return weechat.WEECHAT_RC_ERROR
    conv_id = weechat.buffer_get_string(buffer, "localvar_conversation_id")
    api = {"method": "download", "params": {"options": {"conversation_id": conv_id, "message_id": int(args[0]), "output": args[1]}}}
    ## CHECK r
    r=status.execute_api(api)
    return weechat.WEECHAT_RC_OK

def mark_message_read(conv_id, id):
    api = {"method": "mark", "params": {"options": {"conversation_id": conv_id, "message_id": int(id)}}}
    ## CHECK r
    status.execute_api_bg(api)
    return weechat.WEECHAT_RC_OK

# {"method": "send", "params": {"options": {"channel": {"name": "you,them"}, "message": {"body": "is it cold today?"}}}}
def send_new_message(data, buffer, command):
    args = command.split(' ')
    weechat.prnt("", str(args))
    if len(args) < 3:
        return weechat.WEECHAT_RC_ERROR
    receiver = args[1]
    body = " ".join(args[2:])
    api = {"method": "send", "params": {"options": {"channel": {"name": status.nick_name+','+receiver}, "message": {"body": body}}}}
    r = status.execute_api(api)
    ## I should also search the right buffer but I receive the message so the buffer is created after
    return weechat.WEECHAT_RC_OK_EAT

# }}}
# {"method": "send", "params": {"options": {"channel": {"name": "you,them"}, "message": {"body": "is it cold today?"}, "reply_to": 314}}}
def reply_to_message(data, buffer,command):
    args = command.split(' ')
    weechat.prnt("", str(args))
    if len(args) < 3:
        return weechat.WEECHAT_RC_ERROR
    reply_to = int(args[1])
    body = "".join(args[2:])
    conv_id = weechat.buffer_get_string(buffer, "localvar_conversation_id")
    api = {"method": "send", "params": {"options": {"conversation_id": conv_id, "message": {"body": body}, "reply_to": reply_to}}}
    r = status.execute_api(api)
    return weechat.WEECHAT_RC_OK_EAT

def test12(data, buffer, arg):
    own_lines= weechat.hdata_pointer(weechat.hdata_get("buffer"), buffer, 'own_lines')
    #line = weechat.hdata_pointer(weechat.hdata_get("lines"), own_lines, "last_line")
    #line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")
    #hdata = weechat.hdata_get("line_data")
    #data = weechat.hdata_pointer(hdata.line, pointer, 'data')
    weechat.prnt("",str(own_lines))
    return weechat.WEECHAT_RC_OK

def buffer_switched(data, signal, signal_data):
    plugin = weechat.buffer_get_string(signal_data, "localvar_server")
    if plugin != "KeyBase":
        return weechat.WEECHAT_RC_OK

    first_message = weechat.buffer_get_string(signal_data, "localvar_first_message")
    conv_id = weechat.buffer_get_string(signal_data, "localvar_conversation_id")
    if (first_message == ""):
        weechat.prnt("", "Get history")
        r, f, l = status.get_last_history(conv_id)
        weechat.buffer_set(signal_data, "localvar_set_first_message", str(f))
        weechat.buffer_set(signal_data, "localvar_set_last_message", str(l))
        return weechat.WEECHAT_RC_OK_EAT
    elif first_message != '1':
        weechat.prnt("", "Retrieve others")
    return weechat.WEECHAT_RC_OK_EAT

def window_scrolled(data, signal, signal_data):
    buffer = weechat.current_buffer()
    weechat.prnt("", str(buffer))
    plugin = weechat.buffer_get_string(buffer, "localvar_server")
    weechat.prnt("", plugin)
    if plugin != "KeyBase":
        return weechat.WEECHAT_RC_OK
    first_message = weechat.buffer_get_string(buffer, "localvar_first_message")
    conv_id = weechat.buffer_get_string(buffer, "localvar_conversation_id")
    weechat.prnt("", "first message "+first_message)
    if first_message != "1":
        weechat.prnt("", "retrieve message from "+str(first_message))
        ids = list(range(int(first_message)-25,int(first_message)))
        weechat.prnt("", str(ids))
        status.retrieve_messages_ids(conv_id, ids)
    return weechat.WEECHAT_RC_OK

class status_server:
    def __init__(self, options):
        self.status_name = options['server_name']
        self.nick_name   = options['nickname']
        self.is_away = False;
        global debug
        if options['debug'] == "true":
            debug = True
        else:
            debug = False
        self.private_chans = {}
        self.private_chans_ptr = {}
        self.status = weechat.buffer_new(self.status_name, "status_input_cb", "", "status_close_cb", "")
        weechat.buffer_set(self.status, "localvar_set_type", "server")
        weechat.buffer_set(self.status, "localvar_set_server", "keybase")
        self.init_chats()
        #self.get_history()
        self.reader = weechat.hook_process_hashtable("keybase chat api-listen",
                                                    {"buffer_flush":"1"},0,"start_reading","")
        weechat.hook_command("download", "Download an attachment", "<msg_id> <outputh_path>", "<msg_id>: ID of the message\n<output_path>: Path to store file", "", "download_message", "") 
        weechat.hook_command("open", "Open (with default application) an attachment", "<msg_id>", "<msg_id>: ID of the message\n", "", "open_attachment", "") 
        weechat.hook_command("attach", "Upload file to conversation", "<filename>", "<filename>: File to upload\n", "", "attach_file", "") 
        weechat.hook_command("re", "Reply to message", "<msg_id> <reply_message>", "<msg_id>: ID of the message to which reply\n<reply_message>: reply", "", "reply_message_buffer", "") 
        weechat.hook_command("delete", "Delete message", "<msg_id>", "<msg_id>: ID of the message to which reply", "", "delete_message_buffer", "") 

        ## Hooking to classic weechat command
        weechat.hook_command_run("/msg","send_new_message","") 
        weechat.hook_command_run("/away", "away_command_cb", "")

        weechat.hook_signal("buffer_switch", "buffer_switched", "")
        weechat.hook_signal("window_scrolled", "window_scrolled", "")

    def execute_api(self, api):
        output = subprocess.check_output(['keybase', 'chat', 'api', '-m', json.dumps(api)])
        #weechat.prnt("", "D "+str(output))
        j = json.loads(output)
        if 'error' in j:
            weechat.prnt_date_tags(self.status, 0, "", weechat.prefix("error")+"[X] Error during API "+str(api))
            weechat.prnt(self.status, "Debug: "+str(api))
            return None
        result = json.loads(output)['result']
        return result

    def execute_api_bg(self, api):
        output = subprocess.Popen('keybase chat api -m \'' + json.dumps(api) + '\' &> /tmp/asdasd', shell=True)

    def get_last_history(self, conv_id, notify = ""):
        api = {"method": "read", "params": {"options": {"conversation_id": conv_id }}}
        result=self.execute_api(api)
        mex = {}
        for i in result['messages']:
            date, body, n = handle_message(i['msg'], self.nick_name)
            mex[n] = [date, body]
        od = collections.OrderedDict(sorted(mex.items()))
        for n, b in od.items():
            weechat.prnt_date_tags(self.private_chans[conv_id], b[0],notify ,b[1])
        keys = list(od.keys())
        return None, keys[0],keys[-1] 

    def retrieve_messages_ids(self, conv_id, ids):
        api = {"method": "get", "params": {"options": {"conversation_id": conv_id, "message_ids": ids}}}
        r = self.execute_api(api)
        weechat.prnt("",str(r))

    def retrieve_nth_page(self, conv_id, num=1000, next="", prev=""):
        api = {"method": "read", "params": {"options": {"conversation_id": conv_id , "pagination":{"num":num, "next":next, "previous":prev}}}}
        result = self.execute_api(api)
        return result

    def open_conv_id(self, msg):
        conv_id = msg['conversation_id']
        buff = self.create_new_buffer(msg, conv_id)
        self.private_chans[conv_id] = buff
        self.get_last_history(conv_id)

    def init_chats(self):
        api = {"method":"list"}
        results=self.execute_api(api)
        chats  = results['conversations']
        for chat in chats:
            last_active = int(chat['active_at'])
            system_now = int(time.time())
            # Only create buffers for chat with activity in last 3 months
            if (system_now - last_active < 7776000):
                buff = self.create_new_buffer(chat, chat['id'])
                self.private_chans[chat['id']] = buff

    def create_new_buffer(self, msg, conv_id):
        channel = msg['channel']
        name = channel['name']

        if channel['members_type'] == 'impteamnative' or channel['members_type'] == 'impteamupgrade':
            ## We don't want to replicate our username
            name_splitted = name.split(',')
            ## We can send message to ourself
            if len(name_splitted) == 1:
                buff_name = name
            elif len(name_splitted) == 2:
                if name_splitted[0] == self.nick_name:
                    buff_name = name_splitted[1];
                else:
                    buff_name = name_splitted[0];
            else:
                # buff_name = ",".join(name_splitted[1:])
                buff_name = channel['name']
            ty="private"
        elif channel['members_type'] == 'team':
            buff_name = channel['name']+"#"+channel['topic_name']
            ty="channel"
        else:
            buff_name = "un::"+channel['members_type']
            ty="private"
        buff = weechat.buffer_new(buff_name, "private_input_cb", conv_id, "private_close_cb", conv_id)
        weechat.prnt("", "buffer!"+str(buff));
        weechat.buffer_set(buff, "localvar_set_type", ty)
        weechat.buffer_set(buff, "localvar_set_server", self.status_name)
        weechat.buffer_set(buff, "localvar_set_no_log", "1")
        weechat.buffer_set(buff, "localvar_set_conversation_id", conv_id)
        weechat.buffer_set(buff, "localvar_set_first_message", "")
        weechat.buffer_set(buff, "localvar_set_last_message", "")
        weechat.buffer_set(buff, "unread", "")
        weechat.buffer_set(buff, "notify", "2")
        weechat.buffer_set(buff, "nicklist", "1")
        # Get channel member
        api = {"method": "listmembers", "params": {"options": {"conversation_id": conv_id}}} 
        r=self.execute_api(api)
        nicklist = ["0|Owners", "1|Admins", "2|Writers", "3|Readers", "4|Bot", "5|Restricted Bot"]
        group = [None]*6
        j = 0
        for i in nicklist:
            group[int(j)] = weechat.nicklist_add_group(buff, "", i,"weechat.color.nicklist_group", 1)
            j+=1
        result = r

        # Use @user as username to make autocompletion easier
        for i in result['owners']:
            weechat.nicklist_add_nick(buff, group[0] , '@'+i['username'], "red", "", "lightgreen", 1)
        for i in result['admins']:
            weechat.nicklist_add_nick(buff, group[1] , '@'+i['username'], "red", "", "lightgreen", 1)
        for i in result['writers']:
            weechat.nicklist_add_nick(buff, group[2] , '@'+i['username'], "red", "", "lightgreen", 1)
        for i in result['readers']:
            weechat.nicklist_add_nick(buff, group[3] , '@'+i['username'], "red", "", "lightgreen", 1)
        for i in result['bots']:
            weechat.nicklist_add_nick(buff, group[4] , '@'+i['username'], "red", "", "lightgreen", 1)
        for i in result['restrictedBots']:
            weechat.nicklist_add_nick(buff, group[5] , '@'+i['username'], "red", "", "lightgreen", 1)
        return buff 
# }}}

# =================================[ Main ]================================== {{{
if __name__ == "__main__":
    weechat.register("weebase", "saro", "0.0.1", "GPL3", "Keybase plugin", "", "")
    script_options = {
    "nickname": "",
    "debug": "true",
    "server_name": "KeyBase",
    }
    for option, default_value in script_options.items():
        if not weechat.config_is_set_plugin(option):
            weechat.config_set_plugin(option, default_value)
    PREFIX = "plugins.var.python.weebase."
    script_options['nickname'] = weechat.config_string(weechat.config_get(PREFIX+"nickname"))
    script_options['server_name'] = weechat.config_string(weechat.config_get(PREFIX+"server_name"))
    script_options['debug'] = weechat.config_string(weechat.config_get(PREFIX+"debug"))
    global status 
    #global colors_nick=[
    weechat.prnt("", script_options['nickname'])
    if script_options['nickname'] == "":
        weechat.prnt("", weechat.prefix("error")+"you should set nickname first!")
    else:
        status = status_server(script_options)
# }}} 
