def get_initials(user):
    initials = ""
    if user.first_name:
        initials += user.first_name[0].upper()

    if user.last_name:
        initials += user.last_name[0].upper()

    if len(initials) < 2:
        initials += user.username[0].upper()

    return initials
