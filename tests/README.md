# Recipe tests

Every recipe in this repo, run as a subprocess against a stand-in API — the same
way a customer runs it, so argparse, the `__main__` entry point, file output and
exit codes are all exercised.

```sh
pip install -r requirements.txt pytest   # the published SDK, as a reader installs it
pytest                                   # Python recipes + FastAPI receiver
```

The recipes run against the **installed, published** `speechrevolutions`
package, because that is what a reader gets. To run them against the
python-sdk checkout's `src/` instead (when changing the SDK itself), set
`SR_TEST_SDK_CHECKOUT=1`.

The mock API comes from the `python-sdk` checkout, which is the reference
implementation of the API contract. It is expected beside this repo; point
elsewhere with `pytest --sdk-path /path/to/python-sdk`.

The Express webhook receiver additionally needs a Node harness, and is skipped
without one:

```sh
cd tests/node_harness && npm install   # express + the published speechrevolutions package
```

## Why the recipes need `SPEECHREVOLUTIONS_BASE_URL`

Recipes construct `SpeechRevolutions()` with no arguments, as a reader should.
Without an environment override there is no way to point them anywhere but
production — which is why none of this was testable before. The SDKs now read
`SPEECHREVOLUTIONS_BASE_URL`, symmetric with the API key.
That is also what you want for staging or an egress proxy.
