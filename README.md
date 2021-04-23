# Generate C header file

TBD


## Setup Suggestion

Here's one possible method to try out these scripts.

### Deps

```bash
# See https://python-poetry.org/docs/#installation
wget https://raw.githubusercontent.com/python-poetry/poetry/34d66baa24875bbf799276a8509743cf595ab662/get-poetry.py \
  && echo "5f01d93ab97ace93df972125629a7171 *./get-poetry.py" > get-poetry-py.md5 \
  && md5sum -c ./get-poetry-py.md5 \
  && python3 ./get-poetry.py

# Install project dependencies
poetry install
# Step inside the virtual environment that Poetry setup
poetry shell # or `source ./.venv/activate`
```

Since I'm on Windows, using Bash from "Git for Windows", I run `source ./.venv/Scripts/activate`.

### Run

```bash
python3 ./test/test_gen_header_file.py ./test/accelera-generic_example.rdl
```
