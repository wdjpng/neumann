import pickle
with open('response2.pkl', 'rb') as f:
    data = pickle.load(f)

print(data.output_text)
   
