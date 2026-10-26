# Contributing

- Run `pip install -e '.[test]' && pytest -q` before opening a pull request.
- No runtime dependencies beyond the Python standard library unless there is a strong reason.
- Wording rule: the ledger records that a work *cites* a retracted trial. Never write code or copy that says a work *included* a trial, *relied on* it, or is *wrong*, unless that has been verified and the verification is recorded with its provenance.
- Do not commit the Retraction Watch CSV or OpenAlex dumps. Fetch them at run time.
- Every number in the README must have a source link.
