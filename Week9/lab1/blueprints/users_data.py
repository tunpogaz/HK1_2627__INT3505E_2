"""Single source of data for users."""

USERS = {
    1: {"first_name": "Văn", "last_name": "Nguyễn", "email": "a@vnu.vn"},
    2: {"first_name": "Trang", "last_name": "Trần", "email": "b@vnu.vn"}
}

def get_user(uid):
    return USERS.get(uid)

def add_user(first_name, last_name, email):
    new_id = max(USERS.keys(), default=0) + 1
    user = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email
    }
    USERS[new_id] = user
    return new_id, user

def reset_users():
    """Khôi phục dữ liệu ban đầu cho kiểm thử."""
    global USERS
    USERS = {
        1: {"first_name": "Văn", "last_name": "Nguyễn", "email": "a@vnu.vn"},
        2: {"first_name": "Trang", "last_name": "Trần", "email": "b@vnu.vn"}
    }
