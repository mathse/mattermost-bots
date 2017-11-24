#!/usr/bin/python3

# settings
sleepDuration = 10
domain = 'example.net'
realm = 'example'
groupPrefix = 'example-cc-'
botUsername = 'botUsername'
botPassword = 'botPassword'
mattermostServer = 'mattermost.example.net'
welcomeMsg = {
    'de': 'Hallo %s\nIch habe dich gerade zu den folgenden Teams hinzugefügt: %s',
    'en': 'Hi %s\nI just added you to the following teams: %s'
    }

# imports
from mattermostdriver import Driver
import hashlib
import time

# ldap connector
def ldapGetUserProperties(username):
    global domain, realm, botUsername, botPassword
    from ldap3 import Server, Connection, ALL, NTLM
    server = Server("ldaps://%s" % domain, get_info=ALL)
    l = Connection(server, user="%s\\%s" % (realm,botUsername) , password=botPassword, auto_bind=True)
    l.search("dc=%s" % ',dc='.join(domain.split('.')), "(sAMAccountName=%s)" % username,  attributes=['department', 'sAMAccountName', 'departmentNumber','memberOf'])

    allDepartments = {}
    departmentNumbers = str(l.entries[0].departmentNumber).split(' / ')
    departments = str(l.entries[0].department).split(' / ')
    i = 0
    # locale can be set to de or en
    locale = 'en'
    for departmentNumber in departmentNumbers:
        try:
            departmentName = departments[i]
        except:
            departmentName = "..."
        allDepartments.update({departmentNumber: departmentName})
        i += 1
    return [allDepartments,locale]

foo = Driver({
    'url': mattermostServer,
    'login_id': botUsername,
    'password': botPassword,
    'scheme': 'https',
    'port': 443,
    'basepath': '/api/v4',
    'verify': True,
    'timeout': 30,
})

print("[%s][status] starting mattermost join bot" % int(time.time()))

while 1:
    try:
        foo.login()
    except:
        print("[%s][status] mattermost down" % int(time.time()))
        time.sleep(sleepDuration)
        continue

    bot_object = foo.api['users'].get_user_by_username('mm-bot')

    # get all department teams from mattermost
    teamsInMattermost = []
    for team in foo.api['teams'].get_teams():
        if groupPrefix in team['name']:
            teamsInMattermost.append(team['name'])


    for user in foo.api['users'].get_users():
        if "mm-bot" not in user['username']:
        # if "decker" in user['username']:
            userJoinedTeams = []

            # get all departments of a users from AD
            userDepartmentsInAd, userLocale = ldapGetUserProperties(user['username'])

            # get all departemen teams of a user in Mattermost
            userDepartmentTeamsInMattermost = []
            for team in foo.api['teams'].get_user_teams(user['id']):
                if groupPrefix in team['name']:
                    userDepartmentTeamsInMattermost.append(team['name'])

            # print(mmCcTeams)
            for team in userDepartmentsInAd:
                teamHash = "%s%s" % (groupPrefix,hashlib.md5(team.encode()).hexdigest())

                # do we need to create the team first
                if teamHash not in teamsInMattermost:
                    if "..." not in userDepartmentsInAd[team]:
                        print("[%s][team][create] name: %s, display_name: %s" % (int(time.time()),teamHash,userDepartmentsInAd[team]))
                        foo.api['teams'].create_team(options={
                            'name': teamHash,
                            'display_name': userDepartmentsInAd[team],
                            'type': 'I',
                        })
                        teamsInMattermost.append(teamHash)

                # do we need to add a user to a team
                if teamHash not in userDepartmentTeamsInMattermost:
                    print("[%s][team][join] user: %s, name: %s" % (int(time.time()),user['username'],teamHash))
                    team_id = foo.api['teams'].get_team_by_name(teamHash)['id']
                    foo.api['teams'].add_user_to_team(team_id,options={
                        'team_id': team_id,
                        'user_id': user['id'],
                        'roles': 'team_user'
                    })
                    userJoinedTeams.append(userDepartmentsInAd[team])

            if len(userJoinedTeams) > 0:
                channel = foo.api['channels'].create_direct_message_channel(options=[bot_object['id'],user['id']])
                foo.api['posts'].create_post(options={
                    'channel_id': channel['id'],
                    'message': welcomeMsg[userLocale] % (user['first_name'],', '.join(userJoinedTeams))})

    time.sleep(sleepDuration)
