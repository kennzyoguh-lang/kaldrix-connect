# Contributing

Thank you for helping make agent payments safer.

## Run the tests

```
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
python -m unittest discover -s tests -p "test_*.py"
```

The two files named `e2e_*` run against a live Kaldrix service. They are not needed for most changes.

## Good places to start

* An install guide or example for an assistant or agent framework that is not covered yet
* Clearer wording for a refusal an assistant receives
* A test for a case you think could slip through

## Ground rules

* The connector stays a thin client: decisions belong to the service, never to the assistant.
* Never ask a person for their account key, and never log any key.
* One change per pull request, with a test where it makes sense.

Contributions are accepted under the [Apache License 2.0](LICENSE).

Found a security problem? Please report it privately: see [SECURITY.md](SECURITY.md).
