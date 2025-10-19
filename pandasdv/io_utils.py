import pandas as pd
import io
import sys

df = pd.DataFrame()
original_stdout = sys.stdout
output_buffer = io.StringIO()

def initial_setup(input_file=''):
    global df, original_stdout, output_buffer
    pd.set_option('display.max_columns', None)
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.width', 1000)

    original_stdout = sys.stdout
    output_buffer = io.StringIO()
    sys.stdout = output_buffer

    df = pd.read_spss(input_file, convert_categoricals=False)
    df[df.columns[0]] = df[df.columns[0]].astype(int)
    return df

def output_setup(out_file='python_output.txt'):
    global output_buffer, df
    total_records = df.shape[0]
    print(f"Total number of records: {total_records}")
    sys.stdout = original_stdout
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(output_buffer.getvalue())
    
    print(output_buffer.getvalue())

