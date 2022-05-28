""" Generate and rank guesses to help solve a Wordle puzzle. """

import sys, argparse, requests, re
from copy import copy, deepcopy
from itertools import product
from string import ascii_lowercase

# If the number of zero-frequency guesses <= this threshold, we will
# show the zero-frequency guesses along with those that have non-zero
# frequency
MAX_ZERO_FREQ_GUESSES = 20

# If the number of guesses with non-zero frequency <= this threshold,
# we will also show the zero-frequency guesses
MIN_POS_FREQ_GUESSES = 10 

NUM_TO_ORDSTR = {1:'first', 
		 2:'second',
		 3:'third',
		 4:'fourth',
		 5:'fifth',
		 6:'sixth'}


class GameState:
    def __init__(self):
        self.turn = 0
        self.elim = set() # eliminated letters
        self.green = [None for _ in range(5)] # green letters in position
        self.yellow = [set() for _ in range(5)]	# sets of yellow letters in position
        return

    def increment_turn(self):
        if self.turn == 6:
            msg = "Maximum number of turns reached"
            raise RuntimeError(msg)
        self.turn += 1
        return

def print_guesses(ranked_guesses):
    for i in range(len(ranked_guesses)):
        x = ranked_guesses[i]
        if len(x) == 2:
            guess, score = x
            print(f"{i+1}\t{guess}\t{score}")
        else:
            msg = f"Expected (guess, score), but found this: '{x}'"
            raise RuntimeError(msg)
    return


def present_guesses(ranked_guesses, crit="freq"):
    assert crit in ["freq"], f"Unknown criterion '{crit}'"
    if args.crit == "freq":
        # Filter out zero-frequency guesses if there are any guesses
        # with positive frequency
        pos_freq = []
        zero_freq = []
        for w,f in ranked_guesses:
            if f > 0:
                pos_freq.append((w, f))
            else:
                zero_freq.append((w, f))
        if len(pos_freq):
            print_guesses(pos_freq)
            if len(zero_freq):
                if len(zero_freq) <= MAX_ZERO_FREQ_GUESSES or len(pos_freq) <= MIN_POS_FREQ_GUESSES:
                    line = "-" * (7+len(str(len(pos_freq))))
                    print(line)
                    zero_freq = sorted(zero_freq, key=lambda x:x[0], reverse=False)
                    print_guesses(zero_freq)
                else:
                    print(f"... plus {len(zero_freq)} guesses removed because their frequency is 0.")
            else:
                zero_freq = sorted(zero_freq, key=lambda x:x[0], reverse=False)
                print_guesses(zero_freq)
    return


def generate_ranked_guesses(game_state, crit="freq", fd=None):
    """Identify all possible guesses based on game state, rank, and
    return.

    """
    assert crit in ["freq"], f"Unknown criterion '{crit}'"
    if crit == "freq":
        assert fd is not None, "fd must be provided if criterion is 'freq'"

    # List green positions
    green_pos = [i for i in range(5) if game_state.green[i] is not None]

    # Map yellow letters to positions that are open for them
    ylet_to_open = {}
    for pos, ylet_set in enumerate(game_state.yellow):
        if len(ylet_set):
            for ylet in ylet_set:
                if ylet not in ylet_to_open:
                    ylet_to_open[ylet] = set(range(5)).difference(green_pos)
                ylet_to_open[ylet].remove(pos)
                if not len(ylet_to_open[ylet]):
                    msg = f"No open positions left for letter '{ylet}'"
                    raise RuntimeError(msg)
            
    # Update list of green letters in position using yellow letters
    # that only have one open position left
    for ylet in list(ylet_to_open.keys()):
        openset = ylet_to_open[ylet]
        if len(openset) == 1:
            only_pos = list(openset)[0]
            if game_state.green[only_pos] is not None:
                msg = f"No open positions left for letter '{ylet}'"
                raise RuntimeError(msg)
            game_state.green[only_pos] = ylet
            del ylet_to_open[ylet]

    # Generate all templates using yellow letters that have more than
    # one open position left
    green_template = ['_' if x is None else x for x in game_state.green]
    if not len(ylet_to_open):
        templates = [green_template]
    else:
        templates = []        
        sorted_ylets = sorted(ylet_to_open.keys())
        openlists = [sorted(ylet_to_open[k]) for k in sorted_ylets]
        crossprod = [list(x) for x in list(product(*openlists))]
        poslists = [x for x in crossprod if len(x) == len(set(x))]
        for poslist in poslists:
            template = copy(green_template)
            for ylet, pos in zip(sorted_ylets, poslist):
                template[pos] = ylet
            templates.append(template)

    # Make regex patterns
    nonelim = set(ascii_lowercase).difference(game_state.elim)
    patterns = []
    for i in range(len(templates)):
        for pos in range(5):
            if templates[i][pos] == '_':
                chars = nonelim.difference(game_state.yellow[pos])
                char_class = f"[{''.join(sorted(chars))}]"
                templates[i][pos] = char_class
    for template in templates:
        pattern = re.compile(''.join(template))
        patterns.append(pattern)
      
    # Generate guesses
    guesses = []
    for word in words:
        for p in patterns:
            if p.match(word):
                guesses.append(word)
                break

    # Rank the guesses
    if crit == "freq":
        guesses = [(w,fd[w]) for w in guesses]
        ranked_guesses = sorted(guesses, key=lambda x:x[1], reverse=True)
    return ranked_guesses


def interact(game_state):
    game_state.increment_turn()

    # Generate all possible guesses
    ranked_guesses = generate_ranked_guesses(game_state, crit=args.crit, fd=fd)
    if not len(ranked_guesses):
        msg = "Error: no guesses found"
        raise RuntimeError(msg)

    # Present ranked guesses to user
    present_guesses(ranked_guesses, crit=args.crit)

    # Ask for guess
    turn_ordstr = NUM_TO_ORDSTR[game_state.turn]
    ans = input(f"\nEnter letters of your {turn_ordstr} guess: ").strip().lower()
    assert ans.isalpha() and len(ans) == 5, "Expected 5 letters"
    guess = list(ans)
    ans = input(f"Enter colours returned for your {turn_ordstr} guess ('{ans}'): ").strip()
    assert len(ans) == 5, "Expected 5 digits between 0-2"
    labels = list(ans)
    for label in labels:
        assert label in ['0', '1', '2'], "Expected 5 digits between 0-2"
    if all(x=='2' for x in labels):
        print("\nYou guessed correctly. Congrats!\n")
        sys.exit(0)

    # Update game state
    for position, (letter, label) in enumerate(zip(guess, labels)):
        if label == '0':
            game_state.elim.add(letter)
        elif label == '2':
            if game_state.green[position] is None:	
                game_state.green[position] = letter
                game_state.yellow[position] = set()
                for position in range(5):
                    if letter in game_state.yellow[position]:
                        game_state.yellow[position].remove(letter)
                    else:
                        assert letter == game_state.green[position], "Expected green letters not to change"
            else:
                game_state.yellow[position].add(letter)
    return game_state                               


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--crit", choices = ["freq"], default="freq")
    args = p.parse_args()
    
    # Get word list
    print("\nGetting word list")
    r = requests.get("https://raw.githubusercontent.com/tabatkins/wordle-list/main/words",
                     allow_redirects=True)
    words = set(r.text.split("\n"))
    print(f"Nb words: {len(words)}")        
    
    # Get other resources if required
    if args.crit == "freq":
        print("\nGetting word frequency list")
        r = requests.get("http://corpus.leeds.ac.uk/frqc/internet-en.num",
                         allow_redirects=True)
        lines = r.text.split("\n")
        # skip header
        lines = lines[4:]
        fd = {word:0 for word in words}
        words_found = 0
        for line in lines:
            line = line.strip()
            if len(line):
                elems = line.split()
                if not len(elems) == 3: 
                    print(f"WARNING: skipping line in freq list: Expected 3 space-separated strings in each row, got '{line}'")
                    continue
                rank, rel_freq, word = elems
                rank = int(rank)
                rel_freq = float(rel_freq)
                if word in words:
                    fd[word] = rel_freq
                    words_found += 1
        print(f"{words_found}/{len(words)} words found in frequency list")
    
    # Interact with user
    game_state = GameState()
    for turn in range(6):
        game_state = interact(game_state)

