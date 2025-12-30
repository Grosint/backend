import app.externals.philINT.classes as cl


def philINT_run(email):
    resposne = main(email)
    return resposne


def main(email):
    target_person = cl.Person()
    if email is not None:
        # Email validation is already done upstream, so skipping is_email check
        # if not utils.is_email(email):
        #     print("Email address isn't valid")
        #     exit(0)
        target_email = cl.Email(email_address=email)
        target_email.run_all()
        target_person.fill_from_email(target_email)
    else:
        target_username = cl.Username(username=email)
        target_username.make_connections()
        target_person.fill_from_username(target_username)
    response = target_person.export_raw_data()
    return response
