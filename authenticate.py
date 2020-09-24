from flask import Flask, request, Response

from splitwise_manager import SplitWiseManager


app = Flask(__name__)
sw = SplitWiseManager()


@app.route('/generate_token/')
def index():
    code = request.args.get('code')
    if not code:
        msg = ("'code' not found in get params. This endpoint is meant for the"
               " Splitwise's auth process to call back the app. Are you "
               "accessing it directly?")
        return Response(msg, mimetype='text/plain')
    access_token = sw.get_access_token(code)
    if not access_token:
        msg = ("Failed to generate token with the supplied code parameter. Try"
               " to launch the authentication script again.")
        return Response(msg, mimetype='text/plain')
    print("Token generation finished. Copy the token code inside your .env "
          "file:")
    print(access_token)
    msg = (f"Token generation finished. You can close this tab and go back to "
           f"the console for more instructions.")

    # Stopping the server:
    shutdown_hook = request.environ.get('werkzeug.server.shutdown')
    if shutdown_hook is not None:
        shutdown_hook()
    return Response(msg, mimetype='text/plain')


if __name__ == '__main__':
    print("Launching Splitwise authentication in a browser. Please follow "
          "the steps and come back when finished.")
    sw.launch_authentication()
    # Beware that with debug=True it runs 2 times (2 browser tabs will be
    # open)
    app.run(port=1337, debug=False)
