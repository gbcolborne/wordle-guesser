""" Generate and rank guesses to help solve a Wordle puzzle. """

import sys, argparse, requests, re
from copy import copy, deepcopy
from itertools import product
from string import ascii_lowercase

def print_guesses(ranked_guesses):
    # Present all possible guesses
    for i in range(len(ranked_guesses)):
        x = ranked_guesses[i]
        if len(x) == 2:
            guess, score = x
            print(f"{i+1}\t{guess}\t{score}")
        else:
            msg = f"Expected (guess, score), but found this: '{x}'"
            raise RuntimeError(msg)
    return


def generate_guesses(elim, green, yellow):
    """ Identify all possible guesses based on: set of eliminated letters,
    list of green letters in position, and list of sets of yellow
    letters in position. """

    # List green positions
    green_pos = [i for i in range(5) if green[i] is not None]

    # Map yellow letters to positions that are open for them
    ylet_to_open = {}
    for pos, ylet_set in enumerate(yellow):
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
    for ylet in ylet_to_open.keys():
        openset = ylet_to_open[ylet]
        if len(openset) == 1:
            only_pos = list(openset)[0]
            if green(only_pos) is not None:
                msg = f"No open positions left for letter '{ylet}'"
                raise RuntimeError(msg)
            green[only_pos] = ylet
            del ylet_to_open[ylet]

    # Generate all templates using yellow letters that have more than one open position left
    green_template = ['_' if x is None else x for x in green]
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
    nonelim = set(ascii_lowercase).difference(elim)
    patterns = []
    for i in range(len(templates)):
        for pos in range(5):
            if templates[i][pos] == '_':
                chars = nonelim.difference(yellow[pos])
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
    return guesses
                               

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
        
    elim = set() # Set of eliminated letters
    green = [None] * 5 # List of green letters in position
    yellow = [set() for _ in range(5)] # List of sets of yellow letters in position
    guess_num = 0
    num_to_ordstr = {1:'first', 
                     2:'second',
                     3:'third',
                     4:'fourth',
                     5:'fifth',
                     6:'sixth'}
    for guess_num in range(1,7):
        # Ask for guess
        ans = input(f"\nEnter letters of your {num_to_ordstr[guess_num]} guess: ").strip().lower()
        assert ans.isalpha() and len(ans) == 5, "Expected 5 letters"
        guess = list(ans)
        ans = input(f"Enter colours returned for your {num_to_ordstr[guess_num]} guess ('{ans}'): ").strip()
        assert len(ans) == 5, "Expected 5 digits between 0-2"
        for char in ans:
            assert char in ['0', '1', '2'], "Expected 5 digits between 0-2"
        labels = [int(x) for x in ans]

	# Update data on previous guesses
        for position, (letter, label) in enumerate(zip(guess, labels)):
            
            # Update set of eliminated letters
            if label == 0:
                elim.add(letter)

            # Update list of green letters
            elif label == 2:
                if green[position] is None:
                    green[position] = letter
                else:
                    assert letter == green[position], "Expected green letters not to change"

            # Udpate lists of yellow letters
            elif label == 1:
                yellow[position].add(letter)

        if all(x is not None for x in green):
            msg = "\nYou guessed correctly. Congrats!\n"
            print(msg)
            sys.exit(0)
            
	# Generate all possible guesses
        guesses = generate_guesses(elim, green, yellow)
        if not len(guesses):
            msg = "Error: no guesses found"
            raise RuntimeError(msg)
        
	# Rank the guesses
        if args.crit == "freq":
            # Filter out zero-frequency guesses if there are any
            # guesses with positive frequency
            pos_freq = [(w, fd[w]) for w in guesses if fd[w] > 0]
            if len(pos_freq):
                nb_removed = len(guesses) - len(pos_freq)
                guesses = pos_freq
                
                # Rank
                ranked_guesses = sorted(guesses, key=lambda x:x[1], reverse=True)
                print_guesses(ranked_guesses)
                if len(pos_freq) and nb_removed:
                    print(f"... plus {nb_removed} guesses removed because their frequency is 0.")
            else:
                ranked_guesses = sorted([(w, "?") for w in guesses])
                print_guesses(ranked_guesses)



	
	



