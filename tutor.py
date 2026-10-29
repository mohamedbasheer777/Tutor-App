"""
tutor.py - AI tutor for the Student Learning Companion.

Layer A (always works): concept glossary search (TF-IDF), then quiz notes,
                        plus a review of the student's own mistakes.
Layer B (optional)    : a small local LLM through Ollama, grounded on layer A.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import database
from quiz_data import ALL_QUESTIONS

DEFAULT_MODEL = "llama3.2:1b"
GLOSSARY_MIN_SCORE = 0.12
QUIZ_MIN_SCORE = 0.15

# (subject, topic, title, explanation)
GLOSSARY_RAW = [
    ("Python Programming", "Variables and Data Types", "Variable",
     "A variable is a name that refers to a value stored in memory, for example x = 5. "
     "Python figures out the type automatically, so you do not declare it."),
    ("Python Programming", "Variables and Data Types", "Data types in Python",
     "The main built-in data types are int (whole numbers), float (decimal numbers), "
     "str (text), bool (True or False), list, tuple, dict and set. Use type(x) to check the type."),
    ("Python Programming", "Variables and Data Types", "Mutable and immutable types",
     "Mutable objects can be changed after creation: list, dict, set. Immutable objects "
     "cannot: int, float, str, tuple. Changing an immutable value creates a new object."),
    ("Python Programming", "Loops and Conditions", "if, elif and else",
     "A condition runs code only when it is true. if checks the first condition, elif checks "
     "further conditions, and else runs when none were true. Indentation marks the block."),
    ("Python Programming", "Loops and Conditions", "for loop and range",
     "A for loop repeats code for each item in a sequence. range(n) gives 0 to n-1, and "
     "range(start, stop, step) lets you choose the start and step. The stop value is never included."),
    ("Python Programming", "Loops and Conditions", "while loop, break and continue",
     "A while loop repeats while its condition is true. break exits the loop completely. "
     "continue skips the rest of the current iteration. A loop's else block runs only if break was not used."),
    ("Python Programming", "Functions and Lists", "Function",
     "A function is a reusable block of code defined with def. It can take parameters and "
     "send a value back with return. Without return, a function returns None. "
     "Default arguments are created once, so avoid mutable defaults like lst=[]."),
    ("Python Programming", "Functions and Lists", "List",
     "A list is an ordered, changeable collection written with square brackets. Use x[0] for "
     "the first item, x[-1] for the last, x[1:3] for a slice, append() to add an item, "
     "len(x) for the size, and a list comprehension like [i*i for i in x] to build a new list."),
    ("Data Structures", "Arrays and Linked Lists", "Time complexity and Big O",
     "Big O notation describes how running time grows with input size n. O(1) is constant, "
     "O(log n) grows slowly, O(n) is linear, O(n log n) is typical of good sorting, "
     "and O(n^2) grows quickly."),
    ("Data Structures", "Arrays and Linked Lists", "Array",
     "An array stores items next to each other in memory. Accessing an item by index is O(1). "
     "Inserting or deleting in the middle is O(n) because later items must shift."),
    ("Data Structures", "Arrays and Linked Lists", "Linked list",
     "A linked list is a chain of nodes; each node holds data and a pointer to the next node. "
     "Inserting at the head is O(1) and needs no shifting, but finding an item is O(n) because "
     "you must walk from the head. A cycle can be detected with two pointers moving at different speeds."),
    ("Data Structures", "Stacks and Queues", "Stack",
     "A stack follows LIFO (Last In, First Out). push adds an item on top, pop removes the "
     "top item, and peek looks at it. Uses: undo, function calls, evaluating postfix expressions, "
     "balanced brackets and depth-first search."),
    ("Data Structures", "Stacks and Queues", "Queue",
     "A queue follows FIFO (First In, First Out). enqueue adds at the rear and dequeue removes "
     "from the front. Uses: scheduling, printer jobs and breadth-first search. A circular queue "
     "reuses freed space by wrapping the rear around to the front."),
    ("Data Structures", "Trees and Graphs", "Tree and binary tree",
     "A tree is a hierarchy of nodes. The top node is the root, nodes with no children are leaves. "
     "In a binary tree each node has at most two children, left and right."),
    ("Data Structures", "Trees and Graphs", "Binary search tree (BST)",
     "In a BST, the left subtree holds smaller values and the right subtree holds larger values. "
     "In-order traversal (left, node, right) gives sorted ascending order. Search is O(log n) "
     "when balanced but O(n) when the tree is skewed like a linked list."),
    ("Data Structures", "Trees and Graphs", "Graph, BFS, DFS and Dijkstra",
     "A graph is a set of nodes (vertices) joined by edges. Breadth-first search (BFS) visits "
     "level by level using a queue. Depth-first search (DFS) goes as deep as possible using a stack "
     "or recursion. Dijkstra's algorithm finds shortest paths when edge weights are non-negative."),
    ("Computer Networks", "OSI and TCP/IP Models", "OSI model",
     "The OSI model has 7 layers: Physical, Data Link, Network, Transport, Session, Presentation, "
     "Application. Data units: bits, frames, packets, segments. The Network layer routes with IP, "
     "the Transport layer gives end-to-end delivery with TCP and UDP, the Presentation layer handles "
     "encryption, compression and encoding."),
    ("Computer Networks", "OSI and TCP/IP Models", "TCP/IP model",
     "The original TCP/IP model has 4 layers: Network Access, Internet, Transport, Application. "
     "It is the model actually used on the internet. Some books show a 5-layer version."),
    ("Computer Networks", "IP Addressing", "IP address, IPv4, IPv6 and subnet",
     "An IPv4 address is 32 bits, written as four numbers from 0 to 255. IPv6 is 128 bits. "
     "Class C addresses start with 192 to 223. Private ranges are 10.x.x.x, 172.16.x.x to 172.31.x.x "
     "and 192.168.x.x. A /24 network has 256 addresses, of which 254 are usable for hosts."),
    ("Computer Networks", "Network Protocols", "TCP and UDP",
     "TCP is connection-oriented and reliable: it orders and error-checks data. It starts with "
     "a three-way handshake: SYN, SYN-ACK, ACK. UDP is connectionless and faster but does not "
     "guarantee delivery. Use TCP for web pages and email, UDP for streaming and games."),
    ("Computer Networks", "Network Protocols", "HTTP, HTTPS, DNS, ARP and ports",
     "HTTP transfers web pages on port 80, HTTPS is the secure version on port 443. DNS translates "
     "domain names into IP addresses. ARP maps an IP address to a MAC address on the local network. "
     "FTP uses port 21 and SMTP uses port 25."),
]


def _make_notes():
    notes = []
    for subject, topic, title, text in GLOSSARY_RAW:
        notes.append({
            "subject": subject, "topic": topic, "question": title,
            "answer": text.split(". ")[0].rstrip(".") + ".",
            "explanation": text, "text": f"{title}. {topic}. {text}",
            "kind": "glossary",
        })
    return notes


GLOSSARY = _make_notes()

QUIZ_NOTES = []
for _q in ALL_QUESTIONS:
    _answer = _q["options"][_q["correct_index"]]
    QUIZ_NOTES.append({
        "subject": _q["subject"], "topic": _q["topic"], "question": _q["question"],
        "answer": _answer, "explanation": _q["explanation"],
        "text": f"{_q['topic']}. {_q['question']} {_answer}. {_q['explanation']}",
        "kind": "quiz",
    })


def _index(notes):
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    return vectorizer, vectorizer.fit_transform([n["text"] for n in notes])


_G_VEC, _G_MAT = _index(GLOSSARY)
_Q_VEC, _Q_MAT = _index(QUIZ_NOTES)


def _search(vectorizer, matrix, notes, query, k, min_score):
    scores = cosine_similarity(vectorizer.transform([query]), matrix)[0]
    ranked = sorted(range(len(notes)), key=lambda i: -scores[i])
    return [notes[i] for i in ranked[:k] if scores[i] >= min_score]


def retrieve(query, k=2):
    """Best matching notes: glossary first, quiz notes only as a fallback."""
    if not query.strip():
        return []
    found = _search(_G_VEC, _G_MAT, GLOSSARY, query, k, GLOSSARY_MIN_SCORE)
    if found:
        return found
    return _search(_Q_VEC, _Q_MAT, QUIZ_NOTES, query, k, QUIZ_MIN_SCORE)


def format_notes(notes):
    parts = []
    for n in notes:
        if n["kind"] == "glossary":
            parts.append(f"**{n['question']}** ({n['topic']})\n\n{n['explanation']}")
        else:
            parts.append(f"**{n['topic']}**: {n['question']}\n\n"
                         f"Answer: **{n['answer']}**. {n['explanation']}")
    return "\n\n---\n\n".join(parts)


def builtin_answer(query):
    notes = retrieve(query)
    if not notes:
        return ("I could not find that in my notes. I cover Python basics, loops, functions, "
                "lists, arrays, linked lists, stacks, queues, trees, graphs, the OSI and TCP/IP "
                "models, IP addressing and common protocols. Try a keyword such as *stack*, "
                "*TCP handshake* or *binary search tree*.")
    return format_notes(notes)


# ---------------- Review of the student's own mistakes ----------------
_BY_ID = {q["id"]: q for q in ALL_QUESTIONS}


def recent_mistakes(student_id, limit=5):
    """Questions whose most recent answer was wrong (newest first)."""
    with database.db() as conn:
        rows = conn.execute(
            "SELECT r.question_id, r.selected_index FROM question_responses r "
            "JOIN quiz_attempts a ON a.id = r.attempt_id "
            "WHERE a.student_id = ? ORDER BY a.taken_at DESC, a.id DESC, r.id DESC",
            (student_id,),
        ).fetchall()
    seen, wrong = set(), []
    for row in rows:
        qid = row["question_id"]
        if qid in seen:
            continue
        seen.add(qid)
        q = _BY_ID[qid]
        if row["selected_index"] != q["correct_index"]:
            wrong.append((q, row["selected_index"]))
        if len(wrong) == limit:
            break
    return wrong


def mistakes_answer(student_id):
    wrong = recent_mistakes(student_id)
    if not wrong:
        return ("I found no recent mistakes with saved answers. "
                "Take a quiz first, then ask me again.")
    parts = []
    for q, selected in wrong:
        yours = q["options"][selected] if selected is not None else "no answer"
        parts.append(f"**{q['topic']}**: {q['question']}\n\n"
                     f"You chose: {yours}\n\nCorrect: **{q['options'][q['correct_index']]}**. "
                     f"{q['explanation']}")
    return "Let's review your recent mistakes:\n\n" + "\n\n---\n\n".join(parts)


# ---------------- Layer B: optional local LLM (Ollama) ----------------
def llm_ready():
    """True if the ollama package is installed and the Ollama app is running."""
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def _note_line(n):
    if n["kind"] == "glossary":
        return f"- {n['question']}: {n['explanation']}"
    return f"- {n['question']} Answer: {n['answer']}. {n['explanation']}"


def build_system_prompt(notes, weak_topics):
    weak = ", ".join(weak_topics) if weak_topics else "none detected yet"
    context = "\n".join(_note_line(n) for n in notes) or "- (no matching notes)"
    return (
        "You are a friendly tutor for first-year college students. You only teach Python "
        "Programming, Data Structures and Computer Networks. "
        "RULES: Answer the student's LATEST question directly in your first sentence. "
        "Then explain simply in under 120 words, with one short example if useful. "
        "Use the NOTES below when they are relevant; ignore them if they do not match the "
        "question. If the question is outside these three subjects, say so politely in one "
        "sentence. If you are not sure, say you are not sure. Do not change the subject.\n\n"
        f"NOTES:\n{context}\n\n(Background only, do not mention unless asked: the student's "
        f"weak topics are {weak}.)"
    )


def stream_llm(model, history, notes, weak_topics):
    """Yield text pieces from the local model. Raises on any Ollama problem."""
    import ollama
    messages = [{"role": "system", "content": build_system_prompt(notes, weak_topics)}]
    messages += history[-4:]                      # last two exchanges only
    stream = ollama.chat(model=model, messages=messages, stream=True,
                         options={"temperature": 0.2, "num_predict": 350})
    for chunk in stream:
        yield chunk["message"]["content"]