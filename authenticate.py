from flask import Flask, request, Response

from splitwise_manager import SplitWiseManager


app = Flask(__name__)


@app.route('/test/')
def test():
    print('inside')
    return request.args.get('data', 'Test loaded')  # send text to web browser


@app.route('/generate_token/')
def index():
    """
    So this is going to be called when the user accesses the callback.
    Therefore, we need to trigger the synch from this point, if we got the
    credentials.

    But if we do that here, we have to give the feedback at the web browser.

    Had we have a valid token, we could just run the synch without any
    http server or opening any browser.
    """
    print('args:', request.args)
    sw = SplitWiseManager()
    code = request.args.get('code')
    if not code:
        return request.args.get('data', "'code' not found in get params.")
    access_token = sw.get_access_token(code)
    if not access_token:
        return request.args.get('data', "Failed to generate token with this"
                                        "get['code']")
    print("Access token:")
    print(access_token)
    msg = f"Token generation finished. Token: {access_token}"

    # Trying to stop the server:
    shutdown_hook = request.environ.get('werkzeug.server.shutdown')
    if shutdown_hook is not None:
        shutdown_hook()
    return Response(msg, mimetype='text/plain')


"""
Having the server initialized and listening, we tell the
SplitWiseManager to generate the auth URL and open it in a browser
"""
if __name__ == '__main__':
    print("launching auth..")
    SplitWiseManager().launch_authentication()
    app.run(port=1337, debug=False)
