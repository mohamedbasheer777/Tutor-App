"""
quiz_data.py - Question bank and quiz logic.

Contains:
  1. QUESTION_BANK: 3 subjects x 3 topics x 3 difficulty levels
  2. Helper functions to list subjects/topics and build a quiz
  3. score_quiz(): automatic scoring with explanations

Run this file directly to self-test it:  python quiz_data.py
"""

import random

DIFFICULTIES = ["Easy", "Medium", "Hard"]

# Each question is a tuple:
# (difficulty, question text, [4 options], index of correct option (0-3), explanation)
QUESTION_BANK = {
    # ------------------------------------------------------------------
    "Python Programming": {
        "Variables and Data Types": [
            ("Easy", "Which data type is the value 3.14?",
             ["int", "float", "str", "bool"], 1,
             "Numbers with a decimal point are of type float."),
            ("Easy", "What does type('Hello') return?",
             ["<class 'int'>", "<class 'str'>", "<class 'char'>", "<class 'text'>"], 1,
             "Text in quotes is a string, so its type is str. Python has no separate char type."),
            ("Medium", "What is the result of 7 // 2 in Python?",
             ["3.5", "3", "4", "3.0"], 1,
             "The // operator is floor division. It divides and rounds down, so 7 // 2 = 3."),
            ("Medium", "Which of these data types is mutable (can be changed after creation)?",
             ["tuple", "str", "list", "int"], 2,
             "Lists can be modified in place. Tuples, strings and integers cannot."),
            ("Hard", "What does print(bool('False')) display?",
             ["False", "True", "Error", "None"], 1,
             "Any non-empty string is truthy in Python, even the text 'False'. Only an empty string '' gives False."),
            ("Hard", "What does print(0.1 + 0.2 == 0.3) display?",
             ["True", "False", "Error", "None"], 1,
             "Floating-point numbers are stored approximately, so 0.1 + 0.2 is 0.30000000000000004, not exactly 0.3."),
        ],
        "Loops and Conditions": [
            ("Easy", "Which keyword starts a conditional statement in Python?",
             ["for", "if", "loop", "when"], 1,
             "A condition is written with if (and optionally elif and else)."),
            ("Easy", "How many times does 'for i in range(3):' run its loop body?",
             ["2", "3", "4", "Infinite"], 1,
             "range(3) produces 0, 1, 2, which is 3 values."),
            ("Medium", "What does the break statement do inside a loop?",
             ["Skips the current iteration", "Exits the loop completely",
              "Restarts the loop", "Ends the whole program"], 1,
             "break stops the loop immediately. Skipping one iteration is what continue does."),
            ("Medium", "What does 'for i in range(1, 10, 3): print(i)' print?",
             ["1 4 7", "1 4 7 10", "1 3 6 9", "4 7 10"], 0,
             "range(start, stop, step) starts at 1 and adds 3 each time: 1, 4, 7. The next value, 10, is not below 10."),
            ("Hard", "When does the else block of a for loop run?",
             ["When the loop finishes without hitting break", "Only when the loop hits break",
              "Only if the loop ran zero times", "On every iteration"], 0,
             "A loop's else runs when the loop ends normally. If break is used, the else block is skipped."),
            ("Hard", "How many numbers are printed by: i = 0; while i < 5: i += 2; print(i) "
                     "(the last two statements are inside the loop)?",
             ["2", "3", "4", "5"], 1,
             "i becomes 2, 4, then 6, and each value is printed. After 6 the condition i < 5 is false, so 3 numbers are printed."),
        ],
        "Functions and Lists": [
            ("Easy", "Which keyword is used to define a function in Python?",
             ["function", "def", "fun", "define"], 1,
             "Functions are defined with def, for example: def greet():"),
            ("Easy", "Which function gives the number of items in a list x?",
             ["size(x)", "len(x)", "count(x)", "length(x)"], 1,
             "len() returns the number of items in a list, string, tuple and more."),
            ("Medium", "What is the value of x after: x = [1, 2, 3]; x.append(4)?",
             ["[1, 2, 3, 4]", "[4, 1, 2, 3]", "[1, 2, 3]", "Error"], 0,
             "append() adds the new item at the end of the list."),
            ("Medium", "What does a function return if it has no return statement?",
             ["0", "None", "An empty string", "An error is raised"], 1,
             "Without return, a Python function returns None automatically."),
            ("Hard", "What is the output of print([1, 2, 3, 4, 5][-2:])?",
             ["[4, 5]", "[1, 2]", "[2, 3]", "[5]"], 0,
             "-2: slices from the second-last item to the end, giving [4, 5]."),
            ("Hard", "Given: def f(x, lst=[]): lst.append(x); return lst. "
                     "What does the second call f(2) return, after f(1) was called first?",
             ["[2]", "[1, 2]", "[1]", "Error"], 1,
             "The default list is created only once and shared between calls. This is a famous Python trap, so the list keeps the 1 and becomes [1, 2]."),
        ],
    },
    # ------------------------------------------------------------------
    "Data Structures": {
        "Arrays and Linked Lists": [
            ("Easy", "What is the time complexity of accessing an array element by its index?",
             ["O(1)", "O(n)", "O(log n)", "O(n^2)"], 0,
             "Arrays store items next to each other in memory, so any index is reached in constant time."),
            ("Easy", "Each node of a singly linked list contains data and what else?",
             ["Its array index", "A pointer to the next node", "A hash key", "A pointer to the previous node only"], 1,
             "A singly linked list node stores its data and a reference to the next node."),
            ("Medium", "What is the time complexity of inserting a node at the beginning of a singly linked list?",
             ["O(1)", "O(n)", "O(log n)", "O(n log n)"], 0,
             "Only the new node's pointer and the head need to change, so no traversal is needed."),
            ("Medium", "Which is an advantage of a linked list over an array?",
             ["Faster random access", "Less memory per element",
              "Insertion without shifting elements", "Better cache locality"], 2,
             "Linked lists can insert or delete by changing pointers. Arrays must shift elements."),
            ("Hard", "Why is binary search not efficient on a singly linked list?",
             ["The list is not sorted", "The middle element cannot be reached in constant time",
              "Nodes use extra memory", "Linked lists cannot be searched"], 1,
             "Binary search needs direct access to the middle. A linked list must be walked node by node, which removes the benefit."),
            ("Hard", "Floyd's cycle-detection algorithm for linked lists uses what idea?",
             ["A stack of visited nodes", "Two pointers moving at different speeds",
              "Binary search", "Sorting the nodes first"], 1,
             "A slow pointer moves 1 step and a fast pointer moves 2 steps. If there is a cycle, they eventually meet."),
        ],
        "Stacks and Queues": [
            ("Easy", "Which principle does a stack follow?",
             ["FIFO", "LIFO", "Random order", "Sorted order"], 1,
             "LIFO means Last In, First Out. The most recently added item is removed first."),
            ("Easy", "Which principle does a queue follow?",
             ["LIFO", "FIFO", "Random order", "Sorted order"], 1,
             "FIFO means First In, First Out, like people waiting in a line."),
            ("Medium", "Which stack operation removes the top element?",
             ["push", "pop", "peek", "enqueue"], 1,
             "pop removes and returns the top item. push adds, and peek only looks at it."),
            ("Medium", "Which data structure is normally used to implement Breadth-First Search (BFS)?",
             ["Stack", "Queue", "Heap", "Hash table"], 1,
             "BFS visits nodes level by level, which needs FIFO order, so it uses a queue."),
            ("Hard", "What is the result of the postfix expression: 2 3 4 * +?",
             ["20", "14", "9", "24"], 1,
             "Using a stack: 3 * 4 = 12, then 2 + 12 = 14."),
            ("Hard", "What is the main advantage of a circular queue over a simple array queue?",
             ["It sorts the items", "It reuses the empty space freed by dequeue operations",
              "It can store unlimited items", "It follows LIFO order"], 1,
             "In a circular queue the rear wraps around to the front, so freed slots can be reused."),
        ],
        "Trees and Graphs": [
            ("Easy", "What is the topmost node of a tree called?",
             ["Leaf", "Root", "Branch", "Edge"], 1,
             "The root is the first node of a tree, and it has no parent."),
            ("Easy", "A tree node that has no children is called a:",
             ["Root", "Leaf", "Parent", "Sibling"], 1,
             "Nodes without children are leaf nodes."),
            ("Medium", "An in-order traversal of a Binary Search Tree gives the elements in:",
             ["Random order", "Ascending sorted order", "Descending sorted order", "Level order"], 1,
             "In-order visits left, then node, then right. For a BST this produces sorted ascending order."),
            ("Medium", "What is the maximum number of children a node in a binary tree can have?",
             ["1", "2", "3", "Unlimited"], 1,
             "In a binary tree each node has at most two children: left and right."),
            ("Hard", "What is the worst-case search time in a completely skewed BST with n nodes?",
             ["O(1)", "O(log n)", "O(n)", "O(n log n)"], 2,
             "A skewed BST is like a linked list, so searching may visit all n nodes."),
            ("Hard", "Which algorithm finds the shortest path in a weighted graph with non-negative weights?",
             ["Depth-First Search", "Dijkstra's algorithm", "Kruskal's algorithm", "Bubble sort"], 1,
             "Dijkstra's algorithm finds shortest paths from a source node. Kruskal's finds a minimum spanning tree."),
        ],
    },
    # ------------------------------------------------------------------
    "Computer Networks": {
        "OSI and TCP/IP Models": [
            ("Easy", "How many layers does the OSI model have?",
             ["4", "5", "7", "9"], 2,
             "The OSI model has 7 layers, from Physical up to Application."),
            ("Easy", "Which OSI layer is responsible for routing packets between networks?",
             ["Physical", "Data Link", "Network", "Transport"], 2,
             "The Network layer (Layer 3) handles logical addressing and routing, using IP."),
            ("Medium", "Which OSI layer provides end-to-end delivery using protocols such as TCP and UDP?",
             ["Session", "Transport", "Application", "Network"], 1,
             "The Transport layer (Layer 4) provides end-to-end communication between processes."),
            ("Medium", "How many layers are there in the original TCP/IP model?",
             ["3", "4", "5", "7"], 1,
             "The original TCP/IP model has 4 layers: Network Access, Internet, Transport and Application. Some books show a 5-layer version."),
            ("Hard", "What is the data unit (PDU) at the Data Link layer called?",
             ["Packet", "Segment", "Frame", "Bit"], 2,
             "Data Link: frame. Network: packet. Transport: segment. Physical: bits."),
            ("Hard", "Which OSI layer handles data encryption, compression and translation?",
             ["Session", "Presentation", "Application", "Transport"], 1,
             "The Presentation layer (Layer 6) prepares data, for example by encoding, compressing or encrypting it."),
        ],
        "IP Addressing": [
            ("Easy", "How many bits are there in an IPv4 address?",
             ["16", "32", "64", "128"], 1,
             "IPv4 addresses are 32 bits long, written as four numbers from 0 to 255."),
            ("Easy", "Which of these is a valid IPv4 address?",
             ["192.168.1.256", "192.168.1.1", "192.168.1", "192.168.1.1.1"], 1,
             "An IPv4 address has exactly four numbers, each from 0 to 255."),
            ("Medium", "The address 192.168.1.10 belongs to which class?",
             ["Class A", "Class B", "Class C", "Class D"], 2,
             "Class C covers first numbers 192 to 223."),
            ("Medium", "How many bits are there in an IPv6 address?",
             ["32", "64", "128", "256"], 2,
             "IPv6 addresses are 128 bits long, so there are far more addresses than in IPv4."),
            ("Hard", "How many usable host addresses are there in a /24 IPv4 network?",
             ["256", "254", "255", "252"], 1,
             "A /24 has 256 addresses, but 2 are reserved (network address and broadcast address), leaving 254."),
            ("Hard", "Which of these is a private IP address?",
             ["8.8.8.8", "172.20.5.4", "172.32.0.1", "192.169.1.1"], 1,
             "Private ranges are 10.x.x.x, 172.16.x.x to 172.31.x.x and 192.168.x.x. So 172.20.5.4 is private, while 172.32.0.1 is outside the range."),
        ],
        "Network Protocols": [
            ("Easy", "Which protocol is mainly used to load web pages?",
             ["FTP", "SMTP", "HTTP", "DHCP"], 2,
             "HTTP (HyperText Transfer Protocol) transfers web pages. HTTPS is its secure version."),
            ("Easy", "What does DNS do?",
             ["Encrypts data", "Translates domain names into IP addresses",
              "Assigns MAC addresses", "Sends emails"], 1,
             "DNS works like a phonebook, turning names like example.com into IP addresses."),
            ("Medium", "Which protocol is connection-oriented and reliable?",
             ["UDP", "TCP", "IP", "ICMP"], 1,
             "TCP sets up a connection and guarantees ordered, error-checked delivery. UDP does not."),
            ("Medium", "What is the default port number of HTTPS?",
             ["80", "21", "443", "25"], 2,
             "HTTPS uses port 443. HTTP uses 80, FTP uses 21 and SMTP uses 25."),
            ("Hard", "What does ARP (Address Resolution Protocol) do?",
             ["Maps an IP address to a MAC address", "Maps a domain name to an IP address",
              "Assigns IP addresses automatically", "Encrypts web traffic"], 0,
             "ARP finds the MAC address that belongs to a known IP address on the local network."),
            ("Hard", "What is the correct order of the TCP three-way handshake?",
             ["SYN, SYN-ACK, ACK", "ACK, SYN, FIN", "SYN, ACK, FIN", "FIN, FIN-ACK, ACK"], 0,
             "The client sends SYN, the server replies SYN-ACK, and the client confirms with ACK."),
        ],
    },
}


def _build_question_list():
    """Flatten QUESTION_BANK into a list of dictionaries and check every question."""
    questions = []
    counter = 1
    for subject, topics in QUESTION_BANK.items():
        for topic, items in topics.items():
            for difficulty, text, options, correct_index, explanation in items:
                if difficulty not in DIFFICULTIES:
                    raise ValueError(f"Bad difficulty '{difficulty}' in: {text}")
                if len(options) != 4:
                    raise ValueError(f"Question must have exactly 4 options: {text}")
                if not 0 <= correct_index <= 3:
                    raise ValueError(f"correct_index must be 0-3: {text}")
                questions.append({
                    "id": f"Q{counter:03d}",
                    "subject": subject,
                    "topic": topic,
                    "difficulty": difficulty,
                    "question": text,
                    "options": options,
                    "correct_index": correct_index,
                    "explanation": explanation,
                })
                counter += 1
    return questions


ALL_QUESTIONS = _build_question_list()


# ----------------------------------------------------------------------
# Helper functions used by the app pages
# ----------------------------------------------------------------------
def get_subjects():
    """Return the list of subject names."""
    return list(QUESTION_BANK.keys())


def get_topics(subject):
    """Return the list of topic names for a subject."""
    if subject not in QUESTION_BANK:
        raise ValueError(f"Unknown subject: {subject}")
    return list(QUESTION_BANK[subject].keys())


def get_difficulties(include_mixed=True):
    """Return difficulty choices. 'Mixed' means all difficulty levels together."""
    return (["Mixed"] if include_mixed else []) + DIFFICULTIES


def get_questions(subject, topic, difficulty="Mixed"):
    """Return all matching questions (no shuffling)."""
    if topic not in get_topics(subject):
        raise ValueError(f"Topic '{topic}' does not belong to subject '{subject}'")
    if difficulty != "Mixed" and difficulty not in DIFFICULTIES:
        raise ValueError(f"Unknown difficulty: {difficulty}")
    return [
        q for q in ALL_QUESTIONS
        if q["subject"] == subject
        and q["topic"] == topic
        and (difficulty == "Mixed" or q["difficulty"] == difficulty)
    ]


def build_quiz(subject, topic, difficulty="Mixed", num_questions=6, shuffle=True):
    """
    Build a quiz: a list of question dictionaries.
    If fewer questions exist than requested, all available ones are used.
    """
    pool = get_questions(subject, topic, difficulty)
    quiz = list(pool)
    if shuffle:
        random.shuffle(quiz)
    return quiz[:num_questions]


def score_quiz(quiz, answers):
    """
    Score a quiz automatically.

    quiz    : list of question dictionaries (from build_quiz)
    answers : dict {question_id: chosen option index}. Missing means unanswered.

    Returns a dictionary with score, total, percentage and per-question details.
    """
    details = []
    correct_count = 0
    for q in quiz:
        selected = answers.get(q["id"])
        is_correct = selected is not None and selected == q["correct_index"]
        if is_correct:
            correct_count += 1
        details.append({
            "id": q["id"],
            "question": q["question"],
            "options": q["options"],
            "difficulty": q["difficulty"],
            "selected_index": selected,
            "correct_index": q["correct_index"],
            "is_correct": is_correct,
            "explanation": q["explanation"],
        })
    total = len(quiz)
    percentage = round(correct_count / total * 100, 1) if total else 0.0
    return {
        "score": correct_count,
        "total": total,
        "percentage": percentage,
        "details": details,
    }


# ----------------------------------------------------------------------
# Self-test: run with  python quiz_data.py
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Subjects:", len(get_subjects()))
    print("Topics:", sum(len(get_topics(s)) for s in get_subjects()))
    print("Questions:", len(ALL_QUESTIONS))

    # Every topic must have exactly 2 questions per difficulty level
    for s in get_subjects():
        for t in get_topics(s):
            for d in DIFFICULTIES:
                assert len(get_questions(s, t, d)) == 2, f"Check {s} / {t} / {d}"
    print("Each topic has 2 Easy, 2 Medium and 2 Hard questions: OK")

    quiz = build_quiz("Python Programming", "Loops and Conditions", "Mixed", 6)

    right = {q["id"]: q["correct_index"] for q in quiz}
    r = score_quiz(quiz, right)
    print(f"Test 1 (all correct): {r['score']}/{r['total']} = {r['percentage']}%")
    assert r["percentage"] == 100.0

    wrong = {q["id"]: (q["correct_index"] + 1) % 4 for q in quiz}
    r = score_quiz(quiz, wrong)
    print(f"Test 2 (all wrong): {r['score']}/{r['total']} = {r['percentage']}%")
    assert r["percentage"] == 0.0

    r = score_quiz(quiz, {})
    print(f"Test 3 (no answers): {r['score']}/{r['total']} = {r['percentage']}%")
    assert r["score"] == 0

    print("All quiz_data checks passed.")
    