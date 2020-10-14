def get_tag_from_vk_user_info(user_info: dict) -> str:
    return (
        f"[id{user_info['id']}|"
        f"{user_info['first_name']} "
        f"{user_info['last_name']}]"
    )
