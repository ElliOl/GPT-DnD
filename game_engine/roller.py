"""
D&D Dice Roller
Handles all dice mechanics with true randomness
"""

import random
import re

def roll(dice_string):
    """
    Roll dice using standard D&D notation
    
    Examples:
        roll("1d20") -> 15
        roll("2d6+3") -> 11
        roll("1d20+5") -> 23
        roll("4d6kh3") -> 14 (roll 4d6, keep highest 3 - for stats)
    
    Returns:
        int: The total result
    """
    # Parse dice notation: XdY+Z or XdY-Z
    match = re.match(r'(\d+)d(\d+)(kh\d+)?([+\-]\d+)?', dice_string.lower())
    
    if not match:
        raise ValueError(f"Invalid dice notation: {dice_string}")
    
    num_dice = int(match.group(1))
    die_size = int(match.group(2))
    keep_highest = match.group(3)
    modifier = match.group(4)
    
    # Roll the dice
    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    
    # Handle "keep highest" for ability score generation
    if keep_highest:
        keep_num = int(keep_highest[2:])  # Extract number from "kh3"
        rolls = sorted(rolls, reverse=True)[:keep_num]
    
    total = sum(rolls)
    
    # Add modifier
    if modifier:
        total += int(modifier)
    
    return total

def roll_with_advantage():
    """Roll 2d20 and take the higher (Advantage)"""
    roll1 = random.randint(1, 20)
    roll2 = random.randint(1, 20)
    return max(roll1, roll2)

def roll_with_disadvantage():
    """Roll 2d20 and take the lower (Disadvantage)"""
    roll1 = random.randint(1, 20)
    roll2 = random.randint(1, 20)
    return min(roll1, roll2)

def roll_stats():
    """
    Roll ability scores using standard 4d6 drop lowest
    Returns array of 6 stats
    """
    stats = []
    for _ in range(6):
        stat = roll("4d6kh3")
        stats.append(stat)
    return stats

def death_save():
    """
    Roll a death saving throw
    Returns: "success", "failure", or "critical" (nat 20 = wake up with 1 HP)
    """
    result = random.randint(1, 20)
    
    if result == 20:
        return "critical"
    elif result == 1:
        return "critical_failure"  # Counts as 2 failures
    elif result >= 10:
        return "success"
    else:
        return "failure"

# Quick test
if __name__ == "__main__":
    print("🎲 Dice Roller Tests:")
    print(f"1d20: {roll('1d20')}")
    print(f"2d6+3: {roll('2d6+3')}")
    print(f"1d20+5: {roll('1d20+5')}")
    print(f"Advantage: {roll_with_advantage()}")
    print(f"Disadvantage: {roll_with_disadvantage()}")
    print(f"Ability Scores: {roll_stats()}")
    print(f"Death Save: {death_save()}")
