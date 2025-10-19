# pandas-validator


A Python library to validate survey and structured datasets using pandas.


## Installation
```bash
pip install pandas-validator
```


## Example
```python
from pandas-validator import SR, MULTI, initial_setup


df = initial_setup('survey_data.sav')
SR(Rout='QFILTER', QVAR='Q1', RNG=[1,2,3,4], LIST=['CID','Q1'])
```
