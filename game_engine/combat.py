"""
D&D 5e Combat Engine
"""

from .roller import roll
import random

class CombatEngine:
    def __init__(self):
        self.initiative_order = []
        self.current_turn = 0
        self.round_number = 1
        
    def roll_initiative(self, combatants):
        """
        Roll initiative for all combatants
        
        Args:
            combatants: List of dicts with 'name', 'dex_mod', 'is_player' keys
        
        Returns:
            List of combatants sorted by initiative
        """
        results = []
        
        for combatant in combatants:
            init_roll = roll("1d20") + combatant.get("dex_mod", 0)
            results.append({
                **combatant,
                "initiative": init_roll
            })
        
        # Sort by initiative (highest first), ties broken by dex modifier
        self.initiative_order = sorted(
            results, 
            key=lambda x: (x["initiative"], x.get("dex_mod", 0)), 
            reverse=True
        )
        
        return self.initiative_order
    
    def next_turn(self):
        """Advance to the next turn in combat"""
        self.current_turn += 1
        if self.current_turn >= len(self.initiative_order):
            self.current_turn = 0
            self.round_number += 1
        
        return self.initiative_order[self.current_turn]
    
    def get_current_combatant(self):
        """Get who's turn it is"""
        if not self.initiative_order:
            return None
        return self.initiative_order[self.current_turn]

def attack_roll(attacker, target, advantage=False, disadvantage=False):
    """
    Make an attack roll
    
    Args:
        attacker: Dict with 'attack_bonus' and 'damage_dice'
        target: Dict with 'ac' (armor class)
        advantage/disadvantage: Boolean
    
    Returns:
        Dict with hit status and damage
    """
    # Roll to hit
    if advantage:
        from .roller import roll_with_advantage
        d20 = roll_with_advantage()
    elif disadvantage:
        from .roller import roll_with_disadvantage
        d20 = roll_with_disadvantage()
    else:
        d20 = roll("1d20")
    
    attack_bonus = attacker.get("attack_bonus", 0)
    total = d20 + attack_bonus
    
    # Check for hit
    target_ac = target.get("ac", 10)
    hit = total >= target_ac
    critical = (d20 == 20)
    critical_miss = (d20 == 1)
    
    # Critical always hits, critical miss always misses
    if critical:
        hit = True
    if critical_miss:
        hit = False
    
    damage = 0
    if hit:
        # Roll damage
        damage_dice = attacker.get("damage_dice", "1d6")
        damage_bonus = attacker.get("damage_bonus", 0)
        
        if critical:
            # Critical hits: double the dice (not the modifier)
            damage = roll(damage_dice) + roll(damage_dice) + damage_bonus
        else:
            damage = roll(damage_dice) + damage_bonus
    
    return {
        "d20_roll": d20,
        "attack_total": total,
        "target_ac": target_ac,
        "hit": hit,
        "critical": critical,
        "critical_miss": critical_miss,
        "damage": damage
    }

def apply_damage(character, damage):
    """
    Apply damage to a character
    
    Args:
        character: Dict with 'hp' and 'max_hp'
        damage: Integer amount of damage
    
    Returns:
        Updated character dict with status
    """
    current_hp = character.get("hp", 0)
    new_hp = max(0, current_hp - damage)
    
    character["hp"] = new_hp
    
    status = "alive"
    if new_hp == 0:
        status = "unconscious"
    if new_hp < 0 and abs(new_hp) >= character.get("max_hp", 1):
        status = "instant_death"  # Massive damage rule
    
    return {
        "character": character,
        "damage_taken": damage,
        "current_hp": new_hp,
        "max_hp": character.get("max_hp", 1),
        "status": status
    }

def heal(character, amount):
    """Restore HP to a character"""
    current_hp = character.get("hp", 0)
    max_hp = character.get("max_hp", 1)
    new_hp = min(max_hp, current_hp + amount)
    
    character["hp"] = new_hp
    return character
