from flask import Flask, request, Response

from splitwise_manager import SplitWiseManager


app = Flask(__name__)
sw = SplitWiseManager()


@app.route('/generate_token/')
def index():
    code = request.args.get('code')
    state = request.args.get('state')

    # Callback parameters check
    if not code or not state:
        msg = ("Either or both parameters 'code' and 'state' not found in get."
               " This endpoint is meant for the Splitwise's auth process to "
               "call back the app. Are you accessing it directly?")
        return Response(msg, mimetype='text/html')
    if state != sw.authentication_state:
        msg = ("Supplied 'state' parameter doesn't match the one generated "
               "during authentication initialization. Make sure that you are "
               "using the right tab. If you launched the authentication "
               "multiple times, close all tabs, stop the script, and launch it"
               " again.")
        return Response(msg, mimetype='text/html')

    access_token = sw.get_access_token(code)
    if not access_token:
        msg = ("Failed to generate token with the supplied code parameter. Try"
               " to launch the authentication script again.")
        return Response(msg, mimetype='text/html')
    print("Token generation finished:")
    print(access_token)
    msg = (f"Token generation finished! Your new token is:<br>"
           f"{access_token}<br>"
           "Copy the token to your config.yaml file, at access_token.")

    # Stopping the server:
    shutdown_hook = request.environ.get('werkzeug.server.shutdown')
    if shutdown_hook is not None:
        shutdown_hook()
    return Response(msg, mimetype='text/html')


if __name__ == '__main__':
    print("Launching Splitwise authentication in a browser. Please follow "
          "the steps and come back when finished.")
    sw.launch_authentication()
    # Beware that with debug=True it runs 2 times (2 browser tabs will be
    # open)
    app.run(port=1337, debug=False)
