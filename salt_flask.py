#!/usr/bin/env python
# -*- coding: utf-8 -*- 
#  tanyewei@gmail.com

import flask
from functools import wraps
from flask import Flask, request, abort, make_response, session, render_template, Response
from salt.exceptions import EauthAuthenticationError
import salt.client.api
from redis import Redis
from utils import redis_session
import gevent
import gevent.monkey
from gevent.pywsgi import WSGIServer

gevent.monkey.patch_all()
## app init ##
app = Flask(__name__)

redis = Redis(host='192.168.3.186', port=6379, db=0)
app.session_interface = redis_session.RedisSessionInterface(redis)
app.secret_key = r'''\xd8\x00m\x17O/\xb4\x92o\xa6\xc6\x91\x82q59\x16\xe2;\x8a\xe4\x93\xb9\xc1&+\xad\xe7Y\x11\xe6\x88'''


#设置token
def tokenify(cmd, token=None):
    if token is not None:
        cmd['token'] = token
    return cmd


#登录检查
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('creds', None) is None:
            abort(403, 'login required.')
        if not client.verify_token(session['creds']['token']):
            abort(401, "Invalid token.")
        return f(*args, **kwargs)

    return decorated_function

#登录
@app.route('/login', methods=['POST'])
def login():
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
        session['creds'] = creds
        response = make_response(flask.jsonify({"return": [creds]}))
        response.headers['X-Parachutes'] = 'parachutes are cool'
        return response


#登出
@app.route('/logout', methods=['GET'])
def logout():
    if session.pop('creds', None):
        return 'logout success.'
    return 'nothing to do.'

#run 执行任务
@app.route('/run', defaults={'token': None}, methods=['POST'])
@app.route('/run/<string:token>', methods=['POST'])
@login_required
def run(token):
    cmds = request.json
    if not cmds:
        abort(400, 'Missing command(s).')
    if hasattr(cmds, 'get'):
        cmds = [cmds]
    if not token:
        token = session['creds']['token']
    client = salt.client.api.APIClient()
    try:
        results = [client.run(tokenify(cmd, token)) for cmd in cmds]
    except EauthAuthenticationError as ex:
        abort(401, repr(ex))
    except Exception as ex:
        abort(400, repr(ex))
    return flask.jsonify({"return": results})

#任务查看
class NewAPIClient(salt.client.api.APIClient):
    '''
    继承APIClient，添加一个同步函数，查看所有任务
    '''

    def runner_sync(self, *args, **kwargs):
        return self.runnerClient.cmd(*args, **kwargs)


@app.route('/jobs', defaults={'jid': None}, methods=['GET'])
@app.route('/jobs/<int:jid>', methods=['GET'])
@login_required
def jobs(jid):
    client = NewAPIClient()
    if jid:
        results = client.runner_sync('jobs.lookup_jid', [jid])
        return flask.jsonify({"return": results})
    try:
        results = client.runner_sync('jobs.list_jobs', [])
    except EauthAuthenticationError as ex:
        abort(401, repr(ex))
    except Exception as ex:
        abort(400, repr(ex))
    return flask.jsonify({"return": results})


#event事件
import json


def event_stream():
    yield 'retry: 250\n\n'
    while True:
        data = client.get_event(wait=0.025, tag='', full=True)
        if data:
            yield 'data: {0}\n\n'.format(json.dumps(data))
        else:
            gevent.sleep(0.1)


@app.route('/event')
def event():
    return Response(
        event_stream(),
        mimetype='text/event-stream')


#测试用
@app.route('/test', methods=['GET'])
def test():
    return render_template('index.html')


@app.route('/test1', methods=['GET'])
def test1():
    session['creds'] = 'test'
    return 'login.'


if __name__ == '__main__':
    #client = NewAPIClient()
    app.run(host='0.0.0.0', port=8090, debug=True)