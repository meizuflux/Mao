from secrets import choice
fmt = "**${}**"
_work = (
    'You hand paint to an artist and gain {}',
    'You help a beaver build his dam and he pays you {}',
    'You hold a ladder for an artist and he rewards you with {}',
    'You are given {} for mowing a lawn.',
    'You are paid {} for watering a cactus.',
    'Your friend thanks you with {} for fixing his toilet.',
    'You sell a soccerball at the market for {}',
    'You review the taste of a chocolate chip cookie for {}',
    'You receive an art commission for {}'
    'A neighbor pays {} for housesitting her cat',
    'You sell a friend a GPU for {}',
    'For {}, you voice act for a friends homemade animation',
    'Your homemade lemonade stand results in {}',
    'You paint a fence for {}'
)
def random_message(messages, amount: int):
    return choice(messages).format(fmt.format(amount))
    
def work_message(amount: int):
    return random_message(_work, amount)
