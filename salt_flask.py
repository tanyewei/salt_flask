#!/usr/bin/env python
# -*- coding: utf-8 -*- 
#  tanyewei@gmail.com
## flask import ##
from flask import Flask, request, abort, make_response

## salt import ##
from salt.exceptions import EauthAuthenticationError
import salt.client.api

app = Flask(__name__)


@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/login', methods=['POST'])
def loginPost():
    if request.method == "POST":
        data = request.form
        if not data:
            abort(400, 'Login data missing.')
        creds = dict(
            username=data['username'],
            password=data['password'],
            eauth=data['eauth'],
        )
        client = salt.client.api.APIClient()
        try:
            creds = client.create_token(creds)
        except EauthAuthenticationError as ex:
            abort(401, repr(ex))
        make_response(('X-Auth-Token', creds['token']))
        return {"return": [creds]}


if __name__ == '__main__':
    app.run(debug=True)
