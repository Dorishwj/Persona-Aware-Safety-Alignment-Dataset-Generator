import asyncio
import json
import random
from pathlib import Path
from config import CATEGORIES, TECHNIQUES, ALL_PROFILES, CATEGORY_TECHNIQUE_MAPPING
from engine import build_complete_sample_async


async def process_category(cat_id, total_samples=100):
    """为一个类别生成完整数据集"""
    cat_name = CATEGORIES[cat_id]
    profiles = ALL_PROFILES.get(cat_id, [])
    tech_ids = CATEGORY_TECHNIQUE_MAPPING.get(cat_id, [])

    if not profiles or not tech_ids:
        print(f"跳过类别 {cat_name}：缺少画像或策略配置。")
        return

    print(f"\n>>> 开始生产类别: {cat_name} (预计 {total_samples} 条)")
    results = []

    # 分批次生成，防止 API 速率限制 (每批并发 5 条)
    batch_size = 5
    for i in range(0, total_samples, batch_size):
        tasks = []
        for _ in range(batch_size):
            p = random.choice(profiles)
            t_id = random.choice(tech_ids)
            t_name = TECHNIQUES[t_id]
            tasks.append(build_complete_sample_async(p, t_id, t_name, cat_id, cat_name))

        batch_results = await asyncio.gather(*tasks)
        # 过滤掉生成失败的样本
        valid_samples = [s for s in batch_results if s is not None]
        results.extend(valid_samples)

        # 实时保存，防止中断丢失数据
        file_name = f"dataset_cat_{cat_id}_{cat_name.replace('/', '_')}.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"[{cat_name}] 进度: {len(results)}/{total_samples}")


async def main():
    # 遍历所有 7 个风险类别 (#8 - #14)
    target_categories = [8, 9, 10, 11, 12, 13, 14]

    for cat_id in target_categories:
        await process_category(cat_id, total_samples=100)

    print("\n恭喜！所有类别数据集已构建完成。")


if __name__ == "__main__":
    asyncio.run(main())