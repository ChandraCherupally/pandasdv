from pandasdv import *

df = initial_setup(input_file="Consumer_Brand_Preference_Data_50.sav")

# Print all column names
##print(df.columns.tolist())

##__________________________________________________________________ RespID
print("RespID:")
# Filter and list based on the condition
FLT_LIST(COND=df['RespID'].isna() | (df['RespID']<=0), LIST=['RespID'])

duplicates_cond = df['RespID'].duplicated(keep=False)
print("RespID Duplicate id's checking:")
FLT_LIST(COND=duplicates_cond, LIST=['RespID'])

##___________________________________________________________________ Q1.
SR(Rout='QFILTER', QVAR='Q1', RNG=[1,2])

##___________________________________________________________________ Q2.
print("Q2 checking:")
# Define the condition for filtering
condition = (df['Q1']==2 & ~df['Q2'].isin(lst_no(18,20)))

condition_filter1 = (df['Q1'] == 1) & (~df['Q2'].isin(lst_no(18,100)))
condition_filter2 = (df['Q1'] == 2) & (~df['Q2'].isin(lst_no(18,80)))
condition_filter3 = df['Q2'].isna()

condition = condition_filter1 | condition_filter2 | condition_filter3

# Filter and list based on the condition
FLT_LIST(condition, ['RespID', 'Q1', 'Q2'])

##___________________________________________________________________ Q3.
SR(QVAR='Q3', RNG=[1,2])

##___________________________________________________________________ Q4.
SR(QVAR='Q4', RNG=lst_no(1,4)+[97])


##___________________________________________________________________ Q5.
QVAR = [f'Q5_{i}' for i in lst_no(1,6)]
MULTI(QVAR=QVAR, QEX=['Q5_7'])

##___________________________________________________________________ Q6.
df['QFILTER'] = 0
df.loc[df[['Q5_1','Q5_2','Q5_3','Q5_4','Q5_5','Q5_6']].eq(1).any(axis=1), 'QFILTER'] = 1
QVAR = [f'Q6_{i}' for i in lst_no(1,6)]
MULTI(Rout='QFILTER', QVAR=QVAR, QEX=['Q6_7'])

##___________________________________________________________________ Q7.
for i in lst_no(1,6):
    df['QFILTER'] = 0
    df.loc[df[f'Q6_{i}']==1, 'QFILTER'] = 1
    SR(Rout='QFILTER', QVAR=f'Q7_{i}', RNG=lst_no(1,6), LIST=[f'Q6_{i}'])

##___________________________________________________________________ Q8.
QVAR = [f'Q8_{i}' for i in lst_no(1,9)]+['Q8_98']
MULTI(QVAR=QVAR, QEX=['Q8_97'])

##___________________________________________________________________ Q8_oth.
df['QFILTER'] = 0
df.loc[df['Q8_97']==1, 'QFILTER'] = 1
OETEXT(Rout='QFILTER', QVAR='Q8_oth',LIST=['Q8_97'])

##___________________________________________________________________ Q9.
df['QFILTER'] = 0
df.loc[df[['Q8_1','Q8_2','Q8_3','Q8_4','Q8_5','Q8_6','Q8_7','Q8_8','Q8_9','Q8_97']].eq(1).any(axis=1), 'QFILTER'] = 1

QVAR = [f'Q9_{i}' for i in lst_no(1,5)]
GRID(Rout='QFILTER',QVAR=QVAR, COD=[1, 2, 3, 4, 5], LIST=[])

##___________________________________________________________________ Q10.
df['QFILTER'] = 0
df.loc[df['Q4'].between(1,4), 'QFILTER'] = 1
SR(Rout='QFILTER',QVAR='Q10', RNG=lst_no(1,5),LIST=['Q4'])

##___________________________________________________________________ Q11.
QVAR = [f'Q11_{i}' for i in lst_no(1,7)]
MULTI(QVAR=QVAR, QEX=['Q11_97'])

##___________________________________________________________________ Q12.
SR(QVAR='Q12', RNG=lst_no(1,5))

##___________________________________________________________________ Q13.
QVAR = [f'Q13_{i}' for i in lst_no(1,8)]
MULTI(QVAR=QVAR)

##___________________________________________________________________ Q13_oth.
df['QFILTER'] = 0
df.loc[df['Q13_8']==1, 'QFILTER'] = 1
OETEXT(Rout='QFILTER', QVAR='Q13_oth',LIST=['Q13_8'])

##___________________________________________________________________ Q14_text.
OETEXT(QVAR='Q14_text')


##################################################################### Exporting output
output_setup(out_file='Python_output.txt')

