from __future__ import annotations

import json

SAMPLE_QUESTIONS = [
    {
        "exam_level": "CET4",
        "module": "writing",
        "sub_type": "essay",
        "year": 2024,
        "month": 6,
        "set_no": 1,
        "title": "2024年6月 CET-4 写作：实践能力的重要性",
        "topic": "campus_and_growth",
        "content": {
            "directions": (
                "For this part, you are allowed 30 minutes to write an essay that begins with the sentence "
                "\"Today, more and more college students realize the importance of developing practical skills alongside academic knowledge.\" "
                "You can make statements, give reasons, or cite examples to develop your essay. "
                "You should write at least 120 words but no more than 180 words."
            ),
            "prompt": (
                "Today, more and more college students realize the importance of developing practical skills alongside academic knowledge."
            ),
            "word_limit": "120-180",
            "image_url": None,
        },
        "answer": {
            "reference_essay": (
                "Today, more and more college students realize the importance of developing practical skills alongside academic knowledge. "
                "While theoretical foundations gained in classrooms are indispensable, hands-on competence is often what determines how smoothly "
                "graduates adapt to real-world workplaces.\n\n"
                "There are two main reasons behind this growing awareness. First, employers increasingly value candidates who can apply abstract "
                "concepts to solve concrete problems rather than merely recite textbook definitions. Through internships, lab projects, and student "
                "organizations, undergraduates learn teamwork, communication, and crisis management—abilities rarely mastered through exams alone. "
                "Second, practical experience helps students clarify their career goals early on, enabling them to bridge the gap between campus "
                "life and professional expectations.\n\n"
                "In conclusion, university education should strike a healthy balance between theory and practice. By actively seeking out "
                "real-world opportunities, college students can turn academic knowledge into lasting capability."
            ),
            "key_points": [
                "紧扣给定首句引出话题：理论知识与实践能力并重",
                "正文从就业竞争力（问题解决、团队协作）与职业规划两个维度展开",
                "结尾呼吁平衡理论学习与实践锻炼，字数控制在 120-180 词之间",
            ],
            "scoring_criteria": "按 CET-4 15 分制评分：切题、结构清晰、句式多样且无明显语法拼写错误可得 12-15 分。",
        },
    },
    {
        "exam_level": "CET6",
        "module": "translation",
        "sub_type": "paragraph_translation",
        "year": 2024,
        "month": 12,
        "set_no": 1,
        "title": "2024年12月 CET-6 翻译：新能源汽车与绿色出行",
        "topic": "green_economy_and_technology",
        "content": {
            "directions": (
                "For this part, you are allowed 30 minutes to translate a passage from Chinese into English. "
                "You should write your answer on the Answer Sheet."
            ),
            "source_text": (
                "近年来，中国新能源汽车产业实现了跨越式发展，产销量连续多年位居世界前列。"
                "随着电池技术的不断突破和充电基础设施的日益完善，越来越多的消费者开始选择绿色出行方式。"
                "这不仅显著减少了城市碳排放、改善了空气质量，也为全球应对气候变化和推动可持续发展作出了积极贡献。"
            ),
            "hints": [
                "新能源汽车：new energy vehicles (NEVs)",
                "跨越式发展：leapfrog development / rapid expansion",
                "充电基础设施：charging infrastructure",
            ],
        },
        "answer": {
            "reference_translation": (
                "In recent years, China's new energy vehicle industry has achieved leapfrog development, ranking among the world's top "
                "producers and sellers for consecutive years. With continuous breakthroughs in battery technology and the steady improvement "
                "of charging infrastructure, an increasing number of consumers are opting for green modes of travel. This shift has not only "
                "significantly reduced urban carbon emissions and improved air quality, but also made positive contributions to addressing "
                "global climate change and promoting sustainable development."
            ),
            "key_vocabulary": [
                {"zh": "新能源汽车", "en": "new energy vehicles"},
                {"zh": "跨越式发展", "en": "leapfrog development"},
                {"zh": "位居世界前列", "en": "rank among the top globally"},
                {"zh": "充电基础设施", "en": "charging infrastructure"},
                {"zh": "可持续发展", "en": "sustainable development"},
            ],
            "grammar_notes": (
                "第一句可用现在完成时体现近年来的持续成果，后半句可用分词短语 ranking among... 作伴随状语；"
                "最后一句注意 not only... but also... 的平行结构及主语一致性。"
            ),
        },
    },
    {
        "exam_level": "CET6",
        "module": "reading",
        "sub_type": "careful_reading",
        "year": 2024,
        "month": 6,
        "set_no": 1,
        "title": "2024年6月 CET-6 仔细阅读：数字工具与深度思考",
        "topic": "technology_and_cognition",
        "content": {
            "directions": (
                "There are 2 passages in this section. Each passage is followed by some questions or unfinished statements. "
                "For each of them there are four choices marked A), B), C) and D). You should decide on the best choice."
            ),
            "passage": (
                "When smartphones and instant search engines became ubiquitous, many commentators predicted that offloading routine facts "
                "to digital devices would liberate human minds for higher-order creativity. Yet recent cognitive psychology studies suggest "
                "the picture is more nuanced. When we know information is effortlessly retrievable online, our brains engage in what "
                "researchers call \"cognitive offloading\"—relying on external tools not just to store data, but increasingly to organize "
                "and evaluate arguments.\n\n"
                "In a series of laboratory experiments at a Midwestern university, participants asked to write brief policy analyses with "
                "continuous access to automated summaries produced prose that was grammatically polished but noticeably narrower in perspective "
                "than those who drafted outlines from memory first. Because algorithmic summaries tend to smooth away contradictions, "
                "writers who consulted them prematurely rarely wrestled with the messy ambiguities that spark original insight.\n\n"
                "This does not mean digital assistants should be banished from intellectual work. Rather, timing matters. Researchers found "
                "that when students spent even fifteen minutes formulating independent questions and tentative hypotheses before turning to "
                "digital tools, their final essays retained strong structural originality while still benefiting from rapid fact-checking. "
                "In other words, technology amplifies depth only when human curiosity sets the initial direction.\n\n"
                "Educators are now redesigning assignments around this principle. Instead of banning AI and search tools outright—an approach "
                "that often fails in practice—progressive departments ask students to submit annotated thinking logs showing how their initial "
                "claims evolved after consulting external sources. By making the cognitive journey visible, schools hope to preserve the "
                "productive friction that genuine learning demands."
            ),
            "questions": [
                {
                    "number": 46,
                    "stem": "What did many commentators originally expect from offloading routine facts to digital devices?",
                    "options": {
                        "A": "It would make people overly dependent on search engines.",
                        "B": "It would free up mental capacity for deeper creative thinking.",
                        "C": "It would eliminate grammatical errors in academic writing.",
                        "D": "It would force universities to abandon traditional exams.",
                    },
                },
                {
                    "number": 47,
                    "stem": "What did the Midwestern university experiments reveal about writers who used automated summaries from the start?",
                    "options": {
                        "A": "They finished their policy analyses much faster than expected.",
                        "B": "They struggled to maintain grammatical accuracy in their drafts.",
                        "C": "They showed a narrower range of viewpoints in their writing.",
                        "D": "They were better at identifying contradictions in complex policies.",
                    },
                },
                {
                    "number": 48,
                    "stem": "According to the passage, why do algorithmic summaries hinder original insight when consulted too early?",
                    "options": {
                        "A": "They often contain outdated factual information.",
                        "B": "They tend to gloss over conflicting details and complexities.",
                        "C": "They discourage students from checking primary references.",
                        "D": "They overload working memory with unnecessary statistics.",
                    },
                },
                {
                    "number": 49,
                    "stem": "What does the research suggest is the best way to integrate digital tools into writing?",
                    "options": {
                        "A": "Use digital tools only after forming one's own initial questions.",
                        "B": "Restrict digital access to professional researchers.",
                        "C": "Replace classroom outlining with automated fact-checking.",
                        "D": "Avoid using external tools during the revision stage.",
                    },
                },
                {
                    "number": 50,
                    "stem": "Why are some progressive academic departments requiring annotated thinking logs?",
                    "options": {
                        "A": "To detect unauthorized use of automated summaries.",
                        "B": "To reduce the grading workload for university instructors.",
                        "C": "To keep the challenging mental effort essential to real learning.",
                        "D": "To train students in designing better search algorithms.",
                    },
                },
            ],
        },
        "answer": {
            "correct_answers": {
                "46": "B",
                "47": "C",
                "48": "B",
                "49": "A",
                "50": "C",
            },
            "explanations": {
                "46": "第一段第一句指出，评论者曾预测将日常事实交由数字设备存储会 liberate human minds for higher-order creativity（释放大脑以进行更高层次的创造性思考），对应 B。",
                "47": "第二段第一句提到使用自动摘要的参与者写出的文章 noticeably narrower in perspective（视角明显更窄），对应 C。",
                "48": "第二段第二句说明原因：algorithmic summaries tend to smooth away contradictions，smooth away contradictions 对应 B 中的 gloss over conflicting details。",
                "49": "第三段指出 timing matters，先花 15 分钟独立提出问题和假设再使用数字工具能保留结构原创性，对应 A。",
                "50": "第四段最后一句点明目的：hope to preserve the productive friction that genuine learning demands，对应 C。",
            },
            "synonyms": [
                {"question": "free up mental capacity", "passage": "liberate human minds"},
                {"question": "narrower range of viewpoints", "passage": "narrower in perspective"},
                {"question": "gloss over conflicting details", "passage": "smooth away contradictions"},
                {"question": "challenging mental effort", "passage": "productive friction"},
            ],
        },
    },
    {
        "exam_level": "CET4",
        "module": "reading",
        "sub_type": "banked_cloze",
        "year": 2024,
        "month": 6,
        "set_no": 1,
        "title": "2024年6月 CET-4 选词填空：城市微森林计划",
        "topic": "environment_and_cities",
        "content": {
            "directions": (
                "In this section, there is a passage with ten blanks. You are required to select one word for each blank from a list of "
                "choices given in a word bank following the passage. Read the passage through carefully before making your choices. "
                "Each choice in the bank is identified by a letter. You may not use any of the choices in the bank more than once."
            ),
            "passage": (
                "Across densely populated cities, empty lots and narrow roadside strips are quietly turning into miniature ecosystems known as "
                "urban micro-forests. Unlike traditional parks planted with neat rows of grass and ornamental trees, a micro-forest packs dozens "
                "of native species tightly together so they [26] ______ a dense, self-sustaining woodland within just a few years.\n\n"
                "The method was originally [27] ______ by Japanese botanist Akira Miyawaki, who observed that natural forests recover far faster "
                "when local plants compete for sunlight. Before planting, volunteers enrich the compacted urban soil with organic compost so "
                "roots can [28] ______ deep beneath the surface. Once established, these tiny patches require minimal maintenance and no "
                "chemical fertilizers.\n\n"
                "Environmental planners note that micro-forests offer [29] ______ benefits relative to their modest footprint. On hot summer "
                "afternoons, shaded tree canopies can [30] ______ surrounding street temperatures by several degrees, offering welcome relief "
                "to nearby residents. In addition, the spongy layer of fallen leaves helps absorb heavy rainfall, which reduces the [31] ______ "
                "of sudden street flooding.\n\n"
                "Equally important is their social impact. Because micro-forests can fit into schoolyards or neighborhood corners, local "
                "communities are [32] ______ involved in planting and monitoring them. Children who help water young saplings often develop a "
                "lasting [33] ______ for urban wildlife, from songbirds to pollinating insects. Although micro-forests cannot [34] ______ large "
                "wilderness reserves, they serve as vital stepping stones that [35] ______ nature back into everyday city life."
            ),
            "blank_numbers": [26, 27, 28, 29, 30, 31, 32, 33, 34, 35],
            "word_bank": {
                "A": "actively",
                "B": "appreciation",
                "C": "bring",
                "D": "developed",
                "E": "extend",
                "F": "form",
                "G": "frequently",
                "H": "lower",
                "I": "permanent",
                "J": "remarkable",
                "K": "replace",
                "L": "risk",
                "M": "similar",
                "N": "strictly",
                "O": "survive",
            },
        },
        "answer": {
            "correct_answers": {
                "26": "F",
                "27": "D",
                "28": "E",
                "29": "J",
                "30": "H",
                "31": "L",
                "32": "A",
                "33": "B",
                "34": "K",
                "35": "C",
            },
            "explanations": {
                "26": "so they [form] a dense... woodland：动词原形，意为“形成”一片茂密的林地，选 F (form)。",
                "27": "was originally [developed] by：被动语态，过去分词，“由……开发/创立”，选 D (developed)。",
                "28": "roots can [extend] deep：情态动词后接动词原形，“延伸到地下深处”，选 E (extend)。",
                "29": "offer [remarkable] benefits：修饰名词 benefits 的形容词，“显著的/非凡的益处”，选 J (remarkable)。",
                "30": "can [lower] surrounding street temperatures：动词原形，“降低”周边街道温度，选 H (lower)。",
                "31": "reduces the [risk] of sudden street flooding：名词，reduce the risk of...“降低……的风险”，选 L (risk)。",
                "32": "are [actively] involved in：副词修饰 involved，“积极参与”，选 A (actively)。",
                "33": "develop a lasting [appreciation] for：名词，“培养持久的欣赏/喜爱之情”，选 B (appreciation)。",
                "34": "cannot [replace] large wilderness reserves：动词原形，“无法替代大型荒野保护区”，选 K (replace)。",
                "35": "[bring] nature back into everyday city life：固定搭配 bring ... back into ...“把自然带回日常城市生活”，选 C (bring)。",
            },
        },
    },
]


def seed_sample_questions(db) -> int:
    """Insert built-in sample questions if the questions table is empty."""
    count_row = db.fetchone("SELECT COUNT(*) AS total FROM questions")
    if count_row is None or count_row.get("total", 0) > 0:
        return 0

    inserted = 0
    with db.transaction() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM questions")
        recheck = cur.fetchone()
        if recheck is None or recheck.get("total", 0) > 0:
            return 0
        for item in SAMPLE_QUESTIONS:
            cur.execute(
                """
                INSERT INTO questions (
                    paper_id, exam_level, module, sub_type, year, month, set_no,
                    title, topic, content_json, answer_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    None,
                    item["exam_level"],
                    item["module"],
                    item["sub_type"],
                    item["year"],
                    item["month"],
                    item["set_no"],
                    item["title"],
                    item["topic"],
                    json.dumps(item["content"], ensure_ascii=False),
                    json.dumps(item["answer"], ensure_ascii=False),
                    "published",
                ),
            )
            inserted += 1
    return inserted
