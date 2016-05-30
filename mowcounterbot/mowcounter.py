from .base import MetafetishModuleBase
import redis
import cgi


class MowCounterTransactions(object):
    def __init__(self):
        pass

    def add_sticker_request(self, user_id, file_id):
        pass

    def remove_sticker_request(self, file_id):
        pass

    def add_sticker(self, user_id, file_id, value):
        pass

    def remove_sticker(self, file_id):
        pass

    def get_stickers(self):
        pass

    def update_mow_count(self, user_id, group_id, mow_count):
        pass

    def reset_counts(self):
        pass

    def get_group_list(self):
        pass

    def get_own_count(self, user_id):
        pass

    def get_group_top10(self, group_id):
        pass

    def get_global_top10(self, group_id):
        pass


class MowRedisTransactions(MowCounterTransactions):
    def __init__(self):
        self.redis = redis.StrictRedis(host='pub-redis-13292.us-east-1-4.6.ec2.redislabs.com',
                                       port=13292,
                                       password='stupidbots',
                                       db=0,
                                       decode_responses=True)
        # self.redis = redis.StrictRedis(host='localhost',
        #                                db=0,
        #                                decode_responses=True)

    def add_sticker_request(self, user_id, file_id):
        self.redis.hmset("sticker-requests", {file_id: user_id})

    def remove_sticker_request(self, file_id):
        self.redis.hdel("sticker-requests", file_id)

    def get_sticker_requests(self):
        return self.redis.hgetall("sticker-requests")

    def get_stickers(self):
        return self.redis.hgetall("sticker-values")

    def get_sticker_value(self, sticker_id):
        v = self.redis.hget("sticker-values", sticker_id)
        if v is not None:
            return int(v)
        return None

    def get_user(self, user_id):
        return self.redis.hgetall(user_id)

    def add_sticker(self, user_id, file_id, value):
        self.redis.hset("sticker-values", file_id, value)
        self.redis.hset("sticker-users", file_id, user_id)

    def remove_sticker(self, file_id):
        self.redis.hdel("sticker-values", file_id)
        self.redis.hdel("sticker-users", file_id)

    def get_sticker_values(self):
        return self.redis.hgetall("sticker-values")

    def update_mow_count(self, user_id, user_username, user_fname,
                         user_lname, group_id, group_title, mow_count):
        user_id = str(user_id)
        group_id = str(group_id)
        self.redis.hmset(user_id,
                         {"username": user_username,
                          "first-name": user_fname,
                          "last-name": user_lname})
        self.redis.sadd("groups", group_id)
        self.redis.hmset(group_id, {"title": group_title})
        self.redis.zincrby("user-scores", user_id, mow_count)
        self.redis.zincrby(group_id + "-scores", user_id, mow_count)

    def get_group_list(self):
        return self.redis.smembers("groups")

    def get_group(self, group_id):
        return self.redis.hgetall(group_id)

    def add_group(self, group_id):
        self.redis.sadd("groups", group_id)

    def reset_counts(self):
        self.redis.delete("user-scores")
        groups = self.redis.smembers("groups")
        for g in groups:
            self.redis.delete(g + "-scores")

    def get_own_count(self, user_id, group_id):
        user_id = str(user_id)
        group_id = str(group_id)
        r = {"local_score": 0,
             "local_rank": 0,
             "local_total": 0,
             "global_score": 0,
             "global_rank": 0,
             "global_total": 0}

        # global score
        r["global_score"] = self.redis.zscore("user-scores", user_id)
        if r["global_score"] is None:
            return None
        # global rank
        r["global_rank"] = self.redis.zrevrank("user-scores", user_id)
        # global total
        r["global_total"] = self.redis.zcard("user-scores")

        # local score
        r["local_score"] = self.redis.zscore(group_id + "-scores", user_id)
        # local rank
        r["local_rank"] = self.redis.zrevrank(group_id + "-scores", user_id)
        # local total
        r["local_total"] = self.redis.zcard(group_id + "-scores")
        if not r["local_score"]:
            r["local_score"] = 0
            if not r["local_total"]:
                r["local_total"] = 0
            r["local_rank"] = r["local_total"]
        return r

    def get_group_top10(self, group_id):
        group_id = str(group_id)
        top10 = self.redis.zrevrange(group_id + "-scores", 0, 9,
                                     withscores=True, score_cast_func=int)
        top10list = []
        for (user_id, score) in top10:
            user_dict = {}
            u = self.redis.hgetall(user_id)
            user_dict["name"] = u["first-name"] + u["last-name"]
            user_dict["score"] = score
            top10list.append(user_dict)
        return top10list

    def get_global_top10(self, group_id):
        group_id = str(group_id)
        top10 = self.redis.zrevrange("user-scores", 0, 9,
                                     withscores=True, score_cast_func=int)
        top10list = []
        for (user_id, score) in top10:
            user_dict = {}
            u = self.redis.hgetall(user_id)
            user_dict["name"] = u["first-name"] + u["last-name"]
            user_dict["score"] = score
            top10list.append(user_dict)
        return top10list


class MowMySQLTransactions(MowCounterTransactions):
    pass


class MowCounter(MetafetishModuleBase):
    def __init__(self, dbdir, cm):
        super().__init__(__name__)
        self.store = MowRedisTransactions()
        self.cm = cm

    def rm_sticker(self, bot, update):
        sticker = None
        while True:
            bot.sendMessage(update.message.chat.id,
                            text="Send me the sticker you'd like to add, or /cancel.")
            (bot, update) = yield
            if update.message.sticker is not None:
                sticker = update.message.sticker
                break
            bot.sendMessage(update.message.chat.id,
                            text="That's not a sticker!")
        if sticker.file_id not in self.store.get_stickers().keys():
            bot.sendMessage(update.message.chat.id,
                            text="I don't know that sticker!")
            return
        self.store.remove_sticker(sticker.file_id)
        bot.sendMessage(update.message.chat.id,
                        text="Sticker removed!")

    def check_mows(self, bot, update):
        user = update.message.from_user
        chat = update.message.chat
        mows = 0
        # The API tests for text as either text or '', not None. God damnit.
        if len(update.message.text) is not 0:
            # count mows. Maximum one mow per message
            mows = 1 if update.message.text.lower().count("mow") else 0
        elif update.message.sticker is not None:
            sticker = update.message.sticker
            # Make sure we have the sticker and it's accepted
            value = self.store.get_sticker_value(sticker.file_id)
            if value is None:
                return
            mows = value
        if mows is 0:
            return
        self.store.update_mow_count(user.id, user.username, user.first_name,
                                    user.last_name, chat.id, chat.title, mows)

    def dump(self):
        pass

    def show_own_count(self, bot, update):
        user_id = str(update.message.from_user.id)
        chat_id = str(update.message.chat.id)
        user = update.message.from_user
        r = self.store.get_own_count(user_id, chat_id)
        if r is None:
            bot.sendMessage(update.message.chat.id,
                            text="%s %s has no mows!" % (user.first_name, user.last_name))
            return
        bot.sendMessage(update.message.chat.id,
                        text="%s %s has mowed %d times in this group (Rank: %d of %d), and %d times globally (Rank: %d of %d)." %
                        (user.first_name, user.last_name,
                         r["local_score"], r["local_rank"] + 1, r["local_total"],
                         r["global_score"], r["global_rank"] + 1, r["global_total"]))

    def show_top10_count(self, bot, update):
        chat_id = str(update.message.chat.id)
        group_top10 = self.store.get_group_top10(chat_id)
        global_top10 = self.store.get_global_top10(chat_id)
        msg = "<b>Top 10 Count for Group '%s':</b>\n\n" % update.message.chat.title
        i = 1
        for u in group_top10:
            msg += ("<b>%d.</b> " % (i)) + cgi.escape("%s - %s\n" % (u["name"], u["score"]))
            i += 1
        msg += "\n<b>Top 10 Count Globally:</b>\n\n"
        i = 1
        for u in global_top10:
            msg += ("<b>%d.</b> " % (i)) + cgi.escape("%s - %s\n" % (u["name"], u["score"]))
            i += 1
        bot.sendMessage(update.message.chat.id,
                        text=msg,
                        parse_mode="HTML")

    def list_groups(self, bot, update):
        group_names = []
        for g in self.store.get_group_list():
            try:
                chat = bot.getChat(g)
            except:
                print("Cannot access chat %s?" % g)
                continue
            status = bot.getChatMember(g, bot.id)
            group_names.append("%s - @%s - %s - %s" % (chat.title, chat.username, g, status.status))
        bot.sendMessage(update.message.chat.id,
                        text="Groups I am currently counting mows in:\n %s" % "\n".join(group_names))
        pass

    def list_stickers(self, bot, update):
        bot.sendMessage(update.message.chat.id,
                        text="Here's the list of stickers that count for/against mow counts:")
        for (k, v) in self.store.get_stickers().items():
            bot.sendSticker(update.message.chat.id,
                            k)
            bot.sendMessage(update.message.chat.id,
                            text="^^^^ Sticker Value: %d" % int(v))

    def request_sticker(self, bot, update):
        sticker = None
        while True:
            bot.sendMessage(update.message.chat.id,
                            text="Send me the sticker you'd like to request to be added, or /cancel.")
            (bot, update) = yield
            if update.message.sticker is not None:
                sticker = update.message.sticker
                break
            bot.sendMessage(update.message.chat.id,
                            text="That's not a sticker!")
        if sticker.file_id in self.store.get_stickers().keys() or sticker.file_id in self.store.get_sticker_requests().keys():
            bot.sendMessage(update.message.chat.id,
                            text="I'm already tracking or waiting to review that sticker!")
            return
        self.store.add_sticker_request(update.message.from_user.id,
                                       sticker.file_id)
        bot.sendMessage(update.message.chat.id,
                        text="Sticker requested! The admins will review the sticker and add it if it is mow-worthy. Thanks!")

    def review_stickers(self, bot, update):
        for (sticker_id, user_id) in self.store.get_sticker_requests().items():
            while True:
                bot.sendSticker(update.message.chat.id,
                                sticker_id)
                bot.sendMessage(update.message.chat.id,
                                text="Send 0 to reject sticker, or a pos/neg int to specify sticker value, or /cancel.")
                (bot, update) = yield
                try:
                    value = int(update.message.text)
                    if value != 0:
                        self.store.add_sticker(user_id, sticker_id, value)
                        bot.sendMessage(update.message.chat.id,
                                        text="Sticker added with value %d" % value)
                    self.store.remove_sticker_request(sticker_id)
                    break
                except:
                    continue
        bot.sendMessage(update.message.chat.id,
                        text="Sticker review done!")

    def reset(self, bot, update):
        self.store.reset_counts()
        bot.sendMessage(update.message.chat.id,
                        text="Mow counts reset!")

    def broadcast_message(self, bot, update):
        bot.sendMessage(update.message.chat.id,
                        text="What message would you like to broadcast to groups I'm in?")
        (bot, update) = yield
        message = update.message.text
        groups = self.store.get_group_list()
        for g in groups:
            bot.sendMessage(g,
                            text=message)
