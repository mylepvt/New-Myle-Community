"""30-question Day 2 business evaluation bank (correct = original A/B/C/D key before shuffle).

Answer distribution: A=8, B=8, C=7, D=7  (was: B=16/20 in Q1-20 — fixed)
Q1-20  : A=5, B=5, C=5, D=5  (perfectly even)
Q21-30 : A=3, B=3, C=2, D=2  (MYLE-specific factual questions)
"""
from __future__ import annotations

DAY2_EVAL_QUESTIONS: list[dict] = [
    # ── Q1-20 : Business concepts & mindset (harder, answer distribution even) ──

    {   # Q1 — correct: A
        "id": 1,
        "q": "Job income aur business income ka sabse bada structural fark kya hai?",
        "options": {
            "A": "Job mein time se income tied hai; business mein system se",
            "B": "Job safe hoti hai, business hamesha risky",
            "C": "Job mein low pay hoti hai hamesha",
            "D": "Business mein koi investment nahi chahiye",
        },
        "correct": "A",
    },
    {   # Q2 — correct: D
        "id": 2,
        "q": "Ek person 2,000 hours/year kaam karta hai. Agar woh 5-member team build kare, combined active hours hongi:",
        "options": {
            "A": "2,000",
            "B": "4,000",
            "C": "8,000",
            "D": "10,000",
        },
        "correct": "D",
    },
    {   # Q3 — correct: C
        "id": 3,
        "q": "Traditional retail business mein startup ke waqt sabse bada unavoidable cost kya hota hai?",
        "options": {
            "A": "Digital marketing spend",
            "B": "Employee salary",
            "C": "Capital — rent, inventory, aur setup cost",
            "D": "Accounting software tools",
        },
        "correct": "C",
    },
    {   # Q4 — correct: B
        "id": 4,
        "q": "Business mein 'compounding' ka sabse sahi practical example kya hoga?",
        "options": {
            "A": "Bank FD pe interest milna",
            "B": "Team grow hoti hai — income time ke saath accelerate hoti hai",
            "C": "Har mahine ek fixed bonus milna",
            "D": "Savings account balance badhna",
        },
        "correct": "B",
    },
    {   # Q5 — correct: A
        "id": 5,
        "q": "Agar kisi ne ₹15,000 mein skill seekhi aur 3 mahine mein ₹1,20,000 kamaaye, toh yeh tha:",
        "options": {
            "A": "High-ROI investment",
            "B": "Zyada mehngi course",
            "C": "Sirf luck factor",
            "D": "Short-term gain, long-term mein sustainable nahi",
        },
        "correct": "A",
    },
    {   # Q6 — correct: D
        "id": 6,
        "q": "'Main pehle free mein seekhunga, phir join karunga' — yeh mindset kya indicate karti hai?",
        "options": {
            "A": "Smart aur frugal thinking",
            "B": "Practical financial planning",
            "C": "Research-oriented approach",
            "D": "Low commitment aur clarity ki kami",
        },
        "correct": "D",
    },
    {   # Q7 — correct: C
        "id": 7,
        "q": "Business mein 'system duplication' ka matlab kya hota hai?",
        "options": {
            "A": "Same document do baar print karna",
            "B": "Sirf digital backups maintain karna",
            "C": "Ek proven process sikhao — team bhi wahi independently kare",
            "D": "Software se kaam automate karna",
        },
        "correct": "C",
    },
    {   # Q8 — correct: B
        "id": 8,
        "q": "Ek naukripesh insaan ko 'financial freedom' milna mushkil kyun hoti hai?",
        "options": {
            "A": "Woh mehnat nahi karta",
            "B": "Income time se bound hai — active kaam band toh income band",
            "C": "Market hamesha unstable rehti hai",
            "D": "Tax bahut zyada kaat lete hain",
        },
        "correct": "B",
    },
    {   # Q9 — correct: A
        "id": 9,
        "q": "Job mein income ceiling kyun hoti hai?",
        "options": {
            "A": "Company structure limited raises deta hai — position se upar jaana aasaan nahi",
            "B": "Government ne salary cap lagayi hui hai",
            "C": "Log khud effort nahi karte",
            "D": "Market slow hone se salary nahi badhti",
        },
        "correct": "A",
    },
    {   # Q10 — correct: C
        "id": 10,
        "q": "Investment aur expense mein fundamental fark kya hai?",
        "options": {
            "A": "Investment bada hota hai, expense chhota",
            "B": "Investment hamesha bank mein hoti hai",
            "C": "Investment future mein return create karta hai; expense consume hota hai",
            "D": "Dono consume hote hain — fark sirf tax treatment mein hai",
        },
        "correct": "C",
    },
    {   # Q11 — correct: B
        "id": 11,
        "q": "Kisi ne opportunity samjhi, sab explain kiya, phir bhi decision delay kar diya 'sochne ke liye' — yeh kya indicate karta hai?",
        "options": {
            "A": "Wise aur careful decision-making",
            "B": "Fear ya clarity ki kami",
            "C": "Deep research kar raha hai",
            "D": "Financially strong hai, hurry nahi",
        },
        "correct": "B",
    },
    {   # Q12 — correct: D
        "id": 12,
        "q": "Network business mein 'leverage' practically kis form mein kaam karta hai?",
        "options": {
            "A": "Bank loan lena",
            "B": "Paid advertisements chalana",
            "C": "Social media followers badhana",
            "D": "Team members ki combined effort aur time",
        },
        "correct": "D",
    },
    {   # Q13 — correct: A
        "id": 13,
        "q": "60 saal ki age mein job se retire hone ke baad main financial challenge kya hogi?",
        "options": {
            "A": "Active income band ho jaayegi — savings pe hi depend rehna padega",
            "B": "Sarkar pension mein extra tax kaategi",
            "C": "Property value automatically giregi",
            "D": "Market zaroor crash hoga us waqt",
        },
        "correct": "A",
    },
    {   # Q14 — correct: C
        "id": 14,
        "q": "Bina proper training ke business start karne ka primary risk kya hota hai?",
        "options": {
            "A": "Capital zyada lag jaayega",
            "B": "Government license nahi milega",
            "C": "Foundation weak hoga — wrong actions se failure probability high",
            "D": "Competition bahut zyada mil jaayega",
        },
        "correct": "C",
    },
    {   # Q15 — correct: B
        "id": 15,
        "q": "MYLE mein learning phase kyun zaroori hai consistent success ke liye?",
        "options": {
            "A": "Legal requirement hai certificate ke liye",
            "B": "Bina samjhe system replicate nahi hota — duplication tabhi hogi",
            "C": "Timepass ke liye ek structure diya gaya hai",
            "D": "Coaching fees recover karne ke liye",
        },
        "correct": "B",
    },
    {   # Q16 — correct: D
        "id": 16,
        "q": "'Mujhe pehle results dikhao, phir join karunga' — yeh response kya indicate karta hai?",
        "options": {
            "A": "Smart due diligence kar raha hai",
            "B": "Financial maturity dikha raha hai",
            "C": "Strong research skills hain",
            "D": "Clarity nahi hai ya fear-based hesitation hai",
        },
        "correct": "D",
    },
    {   # Q17 — correct: A
        "id": 17,
        "q": "Passive income develop hone ki primary condition kya hoti hai?",
        "options": {
            "A": "Team independently kaam karne lagti hai — system bina aapke chalta rehta hai",
            "B": "Bank balance ₹10 lakh se upar ho jaaye",
            "C": "Company ka stock market mein list ho",
            "D": "Minimum 5 saal regular job karna zaroori hota hai",
        },
        "correct": "A",
    },
    {   # Q18 — correct: C
        "id": 18,
        "q": "'Calculated risk' aur 'blind risk' mein core difference kya hai?",
        "options": {
            "A": "Calculated risk mein hamesha zyada paisa lagta hai",
            "B": "Blind risk mein guarantee hoti hai result ki",
            "C": "Calculated risk mein information, system aur clarity ke baad decision liya jaata hai",
            "D": "Dono same hain — risk toh risk hi hota hai",
        },
        "correct": "C",
    },
    {   # Q19 — correct: B
        "id": 19,
        "q": "'Main abhi ready nahi hoon' — yeh statement usually kya represent karta hai?",
        "options": {
            "A": "Practical preparation chal rahi hai",
            "B": "Fear-based avoidance ya clarity ki kami",
            "C": "Genuine skill gap hai",
            "D": "Thoughtful financial planning ho rahi hai",
        },
        "correct": "B",
    },
    {   # Q20 — correct: D
        "id": 20,
        "q": "Business successfully build karne ke liye sabse pehla step kya hona chahiye?",
        "options": {
            "A": "Social media accounts banana aur followers badhana",
            "B": "Logo aur branding design karna",
            "C": "Bina seekhe seedha selling start karna",
            "D": "System samajhna aur proper foundation banana",
        },
        "correct": "D",
    },

    # ── Q21-30 : MYLE-specific factual questions ──

    {   # Q21 — correct: A
        "id": 21,
        "q": "FBO ka full form kya hai?",
        "options": {
            "A": "Forever Business Owner",
            "B": "Franchise Business Owner",
            "C": "Fixed Business Operator",
            "D": "Fast Bonus Owner",
        },
        "correct": "A",
    },
    {   # Q22 — correct: B
        "id": 22,
        "q": "Is system mein 'CC' ka matlab kya hai?",
        "options": {
            "A": "Cash Credit",
            "B": "Confirmed Customer / Course Credit",
            "C": "Company Commission",
            "D": "Customer Count",
        },
        "correct": "B",
    },
    {   # Q23 — correct: B
        "id": 23,
        "q": "Assistant Supervisor level ke liye kitne CC required hain?",
        "options": {
            "A": "1 CC",
            "B": "2 CC",
            "C": "5 CC",
            "D": "3 CC",
        },
        "correct": "B",
    },
    {   # Q24 — correct: C
        "id": 24,
        "q": "Supervisor level ke liye kitne CC required hain?",
        "options": {
            "A": "10 CC",
            "B": "15 CC",
            "C": "25 CC",
            "D": "50 CC",
        },
        "correct": "C",
    },
    {   # Q25 — correct: A  (options reshuffled)
        "id": 25,
        "q": "Assistant Manager level ke liye kitne CC required hain?",
        "options": {
            "A": "75 CC",
            "B": "50 CC",
            "C": "100 CC",
            "D": "60 CC",
        },
        "correct": "A",
    },
    {   # Q26 — correct: C
        "id": 26,
        "q": "Manager level ke liye kitne CC required hain?",
        "options": {
            "A": "75 CC",
            "B": "100 CC",
            "C": "120 CC",
            "D": "150 CC",
        },
        "correct": "C",
    },
    {   # Q27 — correct: A  (options reshuffled; value unchanged: 25%)
        "id": 27,
        "q": "Assistant Supervisor level pe joining bonus kitna hota hai?",
        "options": {
            "A": "25%",
            "B": "20%",
            "C": "30%",
            "D": "15%",
        },
        "correct": "A",
    },
    {   # Q28 — correct: D  (options reshuffled; value unchanged: 33%)
        "id": 28,
        "q": "Supervisor level pe discount/bonus kitna hota hai?",
        "options": {
            "A": "25%",
            "B": "30%",
            "C": "38%",
            "D": "33%",
        },
        "correct": "D",
    },
    {   # Q29 — correct: B  (options reshuffled; value unchanged: 43%)
        "id": 29,
        "q": "Manager level pe joining bonus kitna hota hai?",
        "options": {
            "A": "38%",
            "B": "43%",
            "C": "48%",
            "D": "33%",
        },
        "correct": "B",
    },
    {   # Q30 — correct: D
        "id": 30,
        "q": "Ek structured business system mein income kitne types ki hoti hai?",
        "options": {
            "A": "3",
            "B": "5",
            "C": "7",
            "D": "Multiple (layered structured system)",
        },
        "correct": "D",
    },
]

DAY2_EVAL_BY_ID = {q["id"]: q for q in DAY2_EVAL_QUESTIONS}
