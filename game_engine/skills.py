"""
D&D 5e Skill Check System
"""

from .roller import roll, roll_with_advantage, roll_with_disadvantage

# Skill to ability score mapping
SKILL_ABILITIES = {
    "Acrobatics": "dex",
    "Animal Handling": "wis",
    "Arcana": "int",
    "Athletics": "str",
    "Deception": "cha",
    "History": "int",
    "Insight": "wis",
    "Intimidation": "cha",
    "Investigation": "int",
    "Medicine": "wis",
    "Nature": "int",
    "Perception": "wis",
    "Performance": "cha",
    "Persuasion": "cha",
    "Religion": "int",
    "Sleight of Hand": "dex",
    "Stealth": "dex",
    "Survival": "wis"
}

def get_ability_modifier(score):
    """Convert ability score to modifier"""
    return (score - 10) // 2

def skill_check(character, skill_name, dc, advantage=False, disadvantage=False):
    """
    Perform a skill check
    
    Args:
        character: Character dict with abilities and proficiencies
        skill_name: Name of the skill (e.g., "Perception")
        dc: Difficulty Class to beat
        advantage: Roll with advantage (roll twice, take higher)
        disadvantage: Roll with disadvantage (roll twice, take lower)
    
    Returns:
        dict with roll details and success/failure
    """
    # Get the relevant ability score
    ability = SKILL_ABILITIES.get(skill_name, "str")
    ability_score = character.get("abilities", {}).get(ability, 10)
    ability_mod = get_ability_modifier(ability_score)
    
    # Check for proficiency
    proficiencies = character.get("proficiencies", [])
    is_proficient = skill_name.lower() in [p.lower() for p in proficiencies]
    proficiency_bonus = character.get("proficiency_bonus", 2) if is_proficient else 0
    
    # Roll the d20
    if advantage:
        d20_roll = roll_with_advantage()
    elif disadvantage:
        d20_roll = roll_with_disadvantage()
    else:
        d20_roll = roll("1d20")
    
    # Calculate total
    total = d20_roll + ability_mod + proficiency_bonus
    
    # Determine success
    success = total >= dc
    natural_20 = (d20_roll == 20)
    natural_1 = (d20_roll == 1)
    
    # Natural 20 is always a success on skill checks (house rule, not RAW)
    if natural_20:
        success = True
    
    return {
        "roll": d20_roll,
        "ability_modifier": ability_mod,
        "proficiency_bonus": proficiency_bonus,
        "total": total,
        "dc": dc,
        "success": success,
        "natural_20": natural_20,
        "natural_1": natural_1,
        "advantage": advantage,
        "disadvantage": disadvantage
    }

def ability_save(character, ability, dc, advantage=False, disadvantage=False):
    """
    Perform an ability saving throw
    
    Args:
        character: Character dict
        ability: "str", "dex", "con", "int", "wis", or "cha"
        dc: Difficulty Class
    
    Returns:
        dict with roll details
    """
    ability_score = character.get("abilities", {}).get(ability, 10)
    ability_mod = get_ability_modifier(ability_score)
    
    # Check for save proficiency
    save_proficiencies = character.get("save_proficiencies", [])
    is_proficient = ability in save_proficiencies
    proficiency_bonus = character.get("proficiency_bonus", 2) if is_proficient else 0
    
    # Roll
    if advantage:
        d20_roll = roll_with_advantage()
    elif disadvantage:
        d20_roll = roll_with_disadvantage()
    else:
        d20_roll = roll("1d20")
    
    total = d20_roll + ability_mod + proficiency_bonus
    success = total >= dc
    
    return {
        "roll": d20_roll,
        "modifier": ability_mod + proficiency_bonus,
        "total": total,
        "dc": dc,
        "success": success,
        "natural_20": d20_roll == 20,
        "natural_1": d20_roll == 1
    }

# Difficulty Classes reference
DC_EASY = 5
DC_MEDIUM = 10
DC_HARD = 15
DC_VERY_HARD = 20
DC_NEARLY_IMPOSSIBLE = 25
