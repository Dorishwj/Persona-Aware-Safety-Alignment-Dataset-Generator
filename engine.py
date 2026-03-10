import asyncio
import json
import google.generativeai as genai
from config import ATTACKER_SYSTEM_PROMPT, EVALUATOR_SYSTEM_PROMPT, TARGET_SYSTEM_PROMPTS

# 1. 配置Gemini API Key
genai.configure(api_key="xxxx") # 需要输入对应的API key

# 2. 关键：关闭所有内置安全过滤，否则红队攻击生成会被拦截
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


async def call_gemini(system_prompt, user_prompt, model_name="gemini-3.1-flash-lite-preview"):
    """异步调用 Gemini API"""
    # 初始化模型并注入 System Instruction
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
        safety_settings=SAFETY_SETTINGS
    )

    try:
        response = await asyncio.to_thread(
            model.generate_content,
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json" if "分数" in system_prompt else "text/plain"
            )
        )
        return response.text
    except Exception as e:
        print(f"Gemini API 错误: {e}")
        return None


async def build_complete_sample_async(profile, tech_id, tech_name, cat_id, cat_name):
    """单条样本构造逻辑：Attacker -> Target -> Evaluator"""

    # --- 1. Attacker ---
    attacker_user = f"类别: {cat_name}\n策略: {tech_name}\n画像: {json.dumps(profile, ensure_ascii=False)}"
    query = await call_gemini(ATTACKER_SYSTEM_PROMPT, attacker_user, "gemini-2.5-pro")
    if not query: return None

    # --- 2. Target (生成 4 档 Response) ---
    # 这里我们对比不同指令下的防御表现
    modes = ["comply", "strict", "mild", "optimal"]
    response_tasks = [
        call_gemini(TARGET_SYSTEM_PROMPTS[mode], query, "gemini-3.1-flash-lite-preview")
        for mode in modes
    ]
    responses = await asyncio.gather(*response_tasks)

    # --- 3. Evaluator (打分与理由) ---
    score_tasks = [
        call_gemini(EVALUATOR_SYSTEM_PROMPT, f"画像: {profile}\nQuery: {query}\nResponse: {res}", "gemini-3.1-flash-lite-preview")
        for res in responses
    ]
    evals_raw = await asyncio.gather(*score_tasks)

    # 解析 JSON 分数
    scores = []
    for e in evals_raw:
        try:
            data = json.loads(e)
            scores.append(float(data.get("score", 5.0)))
        except:
            scores.append(5.0)

    # --- 4. 组装 ---
    return {
        "query": query,
        "current_personality": profile,
        "technique": tech_name,
        "response": responses[3],  # Optimal
        "reward": scores[3],
        "candidates": [
            [responses[0], scores[0]],  # Unsafe
            [responses[1], scores[1]],  # Robotic
            [responses[2], scores[2]]  # Safe
        ]
    }