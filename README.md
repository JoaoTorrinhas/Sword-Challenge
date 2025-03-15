# Sword-Challenge

# 🏥 Patient Evaluation Logic and Recommendations  

##  Patient Registration Process 
1. **Add new patient**  
   - If the patient is **not** in the database (verified by `first_name` and `last_name`), he or she will be **registered**.

2. **Update existing patient**  
   - If the patient **is already registered**, check if there are any **changes in their data** (`bmi`, `age`, `chronic_pain`, `recent_surgery`, etc.). 
   - If there are changes, the patient data is **updated in the database**.  

3. **Keep data unchanged**  
   - If the patient is already registered and their data **has not changed**, **no action** will be performed.  

##  Recommendations Process
1. **Check existing recommendations**  
   - Before adding new recommendations, check whether **there are already recommendations for the patient on the same day**. 

2. **Reuse recommendations**  
   - If the patient already has recommendations for the current day, they are **returned directly** and **new recommendations are not added**. Only new recommendations (even if the same) are added if it is another day. 

3. **Generate new recommendations**  
   - If there are **no recorded** patient recommendations for the day, **new recommendations are stored** in the database.

##  Motivation for this Logic  
This process reflects real-world scenarios where a patient typically **does not have more than one appointment on the same day with the same or different doctors**.
Appointments take place on separate days and usually with considerable intervals between them.    


## 🏨 Clinical Recommendation Process - The system returns **more than one recommendation** for a patient if necessary, considering their medical conditions.
- The structure of **if statements** is designed so that the **order of recommendations in the list reflects priority**.
- The recommendation **"Post-Op Rehabilitation Plan"** has **higher priority**, while **"Weight Management Program"** has **lower priority**.
- Although this approach is **not essential to the current problem**, it may be **useful in the future** when refining clinical recommendations.
