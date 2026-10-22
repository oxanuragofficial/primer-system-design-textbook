from enum import Enum
from itertools import count

class RequestStatus(Enum):
    UNREAD = 0
    ACCEPTED = 1
    REJECTED = 2

class Message:
    _ids = count(1)
    def __init__(self, sender_id, text):
        self.id, self.sender_id, self.text = next(Message._ids), sender_id, text

class Chat:
    _ids = count(1)
    def __init__(self, users):
        self.id, self.users, self.messages = next(Chat._ids), list(users), []
    def post(self, sender, text):
        if sender not in self.users:
            raise PermissionError("not a member")
        m = Message(sender.id, text)
        self.messages.append(m)
        return m

class PrivateChat(Chat):
    def __init__(self, a, b):
        if a is b:
            raise ValueError("a private chat needs two different users")
        super().__init__([a, b])

class GroupChat(Chat):
    def add_user(self, user):
        if user not in self.users:
            self.users.append(user)
    def remove_user(self, user):
        self.users.remove(user)

class AddRequest:
    def __init__(self, from_user, to_user):
        self.from_user, self.to_user = from_user, to_user
        self.status = RequestStatus.UNREAD

class User:
    def __init__(self, user_id, name):
        self.id, self.name = user_id, name
        self.friends, self.chats, self.incoming = {}, [], []

class UserService:
    def __init__(self):
        self.users = {}
    def add_user(self, user_id, name):
        if user_id in self.users:
            raise ValueError("duplicate id")
        self.users[user_id] = User(user_id, name)
        return self.users[user_id]
    def request_friend(self, from_id, to_id):
        a, b = self.users[from_id], self.users[to_id]
        if a is b or b.id in a.friends:
            raise ValueError("invalid request")
        req = AddRequest(a, b)
        b.incoming.append(req)
        return req
    def answer(self, req, accept):
        if req.status is not RequestStatus.UNREAD:
            raise ValueError("already answered")
        if accept:
            req.status = RequestStatus.ACCEPTED
            req.from_user.friends[req.to_user.id] = req.to_user      # friendship is symmetric
            req.to_user.friends[req.from_user.id] = req.from_user
        else:
            req.status = RequestStatus.REJECTED
    def private_chat(self, a_id, b_id):
        a, b = self.users[a_id], self.users[b_id]
        if b.id not in a.friends:
            raise PermissionError("not friends")
        chat = PrivateChat(a, b)
        a.chats.append(chat); b.chats.append(chat)
        return chat
