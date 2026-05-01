"""Add hunt catalog table

Revision ID: add_hunt_catalog
Revises: 
Create Date: 2025-01-11

"""
import sqlite3

def upgrade():
    """Add hunt_catalog table"""
    conn = sqlite3.connect('/forge/tibia-bestiary/backend/database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hunt_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(200) NOT NULL,
            location VARCHAR(200) NOT NULL,
            level_min INTEGER NOT NULL,
            level_max INTEGER NOT NULL,
            vocation TEXT,
            exp_per_hour INTEGER,
            profit_per_hour INTEGER,
            creatures TEXT NOT NULL,
            strategy TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add some default hunts
    default_hunts = [
        {
            'name': 'Mistrock Cyclopses',
            'location': 'Edron, Mistrock',
            'level_min': 50,
            'level_max': 80,
            'vocation': 'All',
            'exp_per_hour': 400000,
            'profit_per_hour': 50000,
            'creatures': 'Cyclops, Cyclops Smith, Cyclops Drone',
            'strategy': 'Hunt in groups or solo with AoE spells. Great profit from creature products.',
            'notes': 'Bring Fire protection. Can be crowded during double XP events.'
        },
        {
            'name': 'Hellspawn Edron',
            'location': 'Edron Hero Cave',
            'level_min': 100,
            'level_max': 200,
            'vocation': 'EK, RP',
            'exp_per_hour': 800000,
            'profit_per_hour': 100000,
            'creatures': 'Hellspawn, Infernalist',
            'strategy': 'Tank and kill slowly. Use fire protection.',
            'notes': 'Excellent profit. Recommended for Elite Knight with good skills.'
        },
        {
            'name': 'Oramond Minos',
            'location': 'Oramond West',
            'level_min': 80,
            'level_max': 150,
            'vocation': 'All',
            'exp_per_hour': 650000,
            'profit_per_hour': 80000,
            'creatures': 'Minotaur, Minotaur Archer, Minotaur Guard',
            'strategy': 'AoE hunting, good for teams.',
            'notes': 'Voting access required. Very popular spot.'
        },
        {
            'name': 'Glooth Bandits',
            'location': 'Oramond',
            'level_min': 150,
            'level_max': 300,
            'vocation': 'EK, MS, ED',
            'exp_per_hour': 1500000,
            'profit_per_hour': 200000,
            'creatures': 'Glooth Bandit, Glooth Brigand',
            'strategy': 'Team hunt with blocker. Excellent XP and profit.',
            'notes': 'Requires high Oramond votes. Best with team.'
        },
        {
            'name': 'Asuras Palace',
            'location': 'Feyrist',
            'level_min': 200,
            'level_max': 500,
            'vocation': 'EK, MS, ED, RP',
            'exp_per_hour': 3000000,
            'profit_per_hour': 300000,
            'creatures': 'Asura, True Asura',
            'strategy': 'Team hunt. Blocker pulls, shooters kill. Very dangerous.',
            'notes': 'Quest access required. Top tier hunting ground.'
        },
        {
            'name': 'Lower Roshamuul',
            'location': 'Roshamuul',
            'level_min': 250,
            'level_max': 600,
            'vocation': 'All (Team)',
            'exp_per_hour': 4000000,
            'profit_per_hour': 400000,
            'creatures': 'Frazzlemaw, Silencer',
            'strategy': 'Team hunt with good coordination. Pull big groups.',
            'notes': 'Quest access. One of the best spawns in game.'
        },
        {
            'name': 'Issavi Sphinxes',
            'location': 'Issavi',
            'level_min': 150,
            'level_max': 300,
            'vocation': 'All',
            'exp_per_hour': 1800000,
            'profit_per_hour': 150000,
            'creatures': 'Sphinx, Lamassu',
            'strategy': 'Can hunt solo or team. Watch out for strong spells.',
            'notes': 'Good balance between XP and profit.'
        },
        {
            'name': 'Spectres Edron',
            'location': 'Edron',
            'level_min': 130,
            'level_max': 200,
            'vocation': 'MS, ED',
            'exp_per_hour': 1000000,
            'profit_per_hour': 120000,
            'creatures': 'Spectre, Ghost, Phantasm',
            'strategy': 'Solo mage hunt. Use energy spells.',
            'notes': 'Classic mage hunting ground. Can be profitable.'
        }
    ]
    
    for hunt in default_hunts:
        cursor.execute('''
            INSERT INTO hunt_catalog (name, location, level_min, level_max, vocation, exp_per_hour, profit_per_hour, creatures, strategy, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (hunt['name'], hunt['location'], hunt['level_min'], hunt['level_max'], hunt['vocation'], 
              hunt['exp_per_hour'], hunt['profit_per_hour'], hunt['creatures'], hunt['strategy'], hunt['notes']))
    
    conn.commit()
    conn.close()
    print("✅ Hunt catalog table created and populated with default hunts")

if __name__ == '__main__':
    upgrade()
