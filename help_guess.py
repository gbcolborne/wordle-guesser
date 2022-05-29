""" Generate and rank guesses to help solve a Wordle puzzle. """

import sys, argparse, requests, re
from collections import defaultdict
from copy import copy, deepcopy
from itertools import product
from string import ascii_lowercase

# Max guesses shown
MAX_GUESSES_SHOWN = 100
NUM_TO_ORDSTR = {1:'first',
                 2:'second',
                 3:'third',
                 4:'fourth',
                 5:'fifth',
                 6:'sixth'}

class GameState:
    def __init__(self):
        self.turn = 1 # Turn
        self.elim = set() # eliminated letters
        self.green = [None for _ in range(5)] # green letters in position
        self.yellow = {} # Maps yellow letters to positions that were tried
        return

    def copy(self):
        return deepcopy(self)

    def increment_turn(self):
        if self.turn == 6:
            msg = "Maximum number of turns exceded"
            raise RuntimeError(msg)
        self.turn += 1
        return

    def letter_in_yellow(self, letter):
        return letter in self.yellow

    def yellow_letters(self):
        return set(self.yellow.keys())

    def remove_letter_from_yellow(letter):
        del self.yellow[letter]
        return

    def update(self, guess, labels, increment_turn=True):
        if increment_turn:
            self.increment_turn()
        green_here = defaultdict(list)
        yellow_here = defaultdict(list)
        grey_here = defaultdict(list)
        for position, (letter, label) in enumerate(zip(guess, labels)):
            if label == '0':
                grey_here[letter].append(position)
            elif label == '1':
                yellow_here[letter].append(position)
            elif label == '2':
                green_here[letter].append(position)
        for letter, positions in grey_here.items():
            self.elim.add(letter)
        for letter, positions in yellow_here.items():
            if letter not in self.yellow:
                self.yellow[letter] = set()
            for position in positions:
                self.yellow[letter].add(position)        
        for letter, positions in green_here.items():
            for position in positions:
                if self.green[position] is not None:
                    if letter != self.green[position]:
                        msg = "Expected green letters not to change"
                        raise RuntimeError(msg)
                else:
                    self.green[position] = letter
                    if letter in self.yellow:
                        if letter in yellow_here:
                            if position in self.yellow[letter]:
                                self.yellow[letter].remove(position)
                        else:
                            del self.yellow[letter]
        return
    
    def get_tried_yellows_for_position(self, position):
        assert position in range(5)
        yellows = set()
        for letter, tried in self.yellow.items():
            if position in tried:
                yellows.add(letter)
        return yellows

    def generate_guesses(self):
        """Identify all possible guesses based on game state."""
    
        # List green positions
        green_pos = [i for i in range(5) if self.green[i] is not None]
    
        # Map yellow letters to positions that are open for them
        ylet_to_open = {}
        for letter, tried in game_state.yellow.items():
            ylet_to_open[letter] = set(range(5)).difference(tried).difference(green_pos) 
            if not len(ylet_to_open[letter]):
                msg = f"No open positions left for letter '{ylet}'"
                raise RuntimeError(msg)
    
        # Check if we have found any new green position,
        # i.e. positions that are the last valid position for a yellow
        # letter
        green_found = [None for _ in range(5)]
        for ylet in list(ylet_to_open.keys()):
            openset = ylet_to_open[ylet]
            if len(openset) == 1:
                only_pos = list(openset)[0]
                if self.green[only_pos] is not None:
                    msg = f"No open positions left for letter '{ylet}'"
                    raise RuntimeError(msg)
                green_found[only_pos] = ylet
                del ylet_to_open[ylet]
    
        # Generate all templates using yellow letters that have more
        # than one open position left
        green_template = ['_' if x is None else x for x in self.green]
        for pos, letter in enumerate(green_found):
            if letter is not None:
                green_template[pos] = letter
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
        nonelim = set(ascii_lowercase).difference(self.elim)
        patterns = []
        for i in range(len(templates)):
            for pos in range(5):
                if templates[i][pos] == '_':
                    tried = self.get_tried_yellows_for_position(pos)                
                    chars = nonelim.difference(tried)
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
        return guesses, green_found

    def generate_ranked_guesses(self, wordfreq, Lambda):
        """Identify all possible guesses based on game state, rank, and
        return.

        """
        guesses, green_found = self.generate_guesses()
        
        # Assume each guess is wrong, and generate next guesses
        # for each. Compute reduction of search space.
        labels = ['0' for _ in range(5)]
        for pos in range(5):
            if self.green[pos] is not None or green_found[pos] is not None:
                labels[pos] == '2'
        space_redux = {}
        for gix, g in enumerate(guesses):
            next_state = self.copy()
            next_state.update(g, labels)
            next_guesses, _ = next_state.generate_guesses()
            # Initial score is reduction of search space assuming guess is wrong 
            space_redux[g] = (len(guesses) - len(next_guesses)) / len(guesses)
            if (gix+1) % 100 == 0:
                print(f"Nb guesses scored: {gix+1}/{len(guesses)}")
        scored_guesses = []
        for g in guesses:
            score = Lambda * space_redux[g] + ((1 - Lambda) * wordfreq[g])
            scored_guesses.append((g, score))
        print(f"Nb guesses scored: {gix+1}/{len(guesses)}")
        ranked_guesses = sorted(scored_guesses, key=lambda x:x[1], reverse=True)
        return ranked_guesses, space_redux

def present_guesses(ranked_guesses, wordfreq, space_redux):
    nb_shown = min(MAX_GUESSES_SHOWN, len(ranked_guesses))
    for i in range(nb_shown):
        guess_num = i + 1
        x = ranked_guesses[i]
        if len(x) == 2:
            guess, score = x
            print(f"{guess_num}\t{guess}\t{score:.4f} (space-redux={space_redux[guess]:.4f}, freq={wordfreq[guess]:.4f})")
        else:
            msg = f"Expected (guess, score), but found this: '{x}'"
            raise RuntimeError(msg)
    if len(ranked_guesses) > nb_shown:
        print(f"... plus {len(ranked_guesses)-nb_shown} lower-ranked guesses")
    return


def interact(game_state, wordfreq, Lambda):
    # Generate all possible guesses
    ranked_guesses, space_redux = game_state.generate_ranked_guesses(wordfreq, Lambda)
    if not len(ranked_guesses):
        msg = "Error: no guesses found"
        raise RuntimeError(msg)

    # Present ranked guesses to user
    present_guesses(ranked_guesses, wordfreq, space_redux)

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

    # Update game state and return
    game_state.update(guess, labels, increment_turn=True)
    return game_state                               

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--Lambda",
                   type=float,
                   default=0.5,
                   help="coefficient of scoring function (> 0.5 will weight space-redux more heavily)")
    args = p.parse_args()
    assert args.Lambda >= 0 and args.Lambda <= 1, "lambda must be between 0 and 1"
    
    # Get word list
    print("\nGetting word list")
    r = requests.get("https://raw.githubusercontent.com/tabatkins/wordle-list/main/words",
                     allow_redirects=True)
    words = set(r.text.split("\n"))
    print(f"Nb words: {len(words)}")        
    
    # Get word frequency list
    print("\nGetting word frequency list")
    r = requests.get("http://corpus.leeds.ac.uk/frqc/internet-en.num",
                     allow_redirects=True)
    lines = r.text.split("\n")
    # skip header
    lines = lines[4:]
    word2freq = {word:0 for word in words}
    words_found = 0
    for line in lines:
        line = line.strip()
        if len(line):
            elems = line.split()
            if not len(elems) == 3: 
                print(f"WARNING: skipping line in freq list: Expected 3 space-separated strings in each row, got '{line}'")
                continue
            rank, freq, word = elems
            rank = int(rank)
            freq = float(freq)
            if word in words:
                word2freq[word] = freq
                words_found += 1
    print(f"{words_found}/{len(words)} words found in frequency list")

    # Normalize
    max_freq = max(word2freq.values())
    norm_word2freq = {w:f/max_freq for (w,f) in word2freq.items()} 
        
    # Interact with user
    game_state = GameState()
    for turn in range(6):
        game_state = interact(game_state, norm_word2freq, args.Lambda)

