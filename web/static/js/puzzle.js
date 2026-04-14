/* Chess Puzzle Trainer — client-side logic */

var board = null;   // chessboard.js instance
var game  = null;   // chess.js instance
var currentPuzzle = null;
var puzzleActive  = false;

var stats = { attempted: 0, correct: 0 };

var PIECE_THEME =
  'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png';

// ── Initialise ──────────────────────────────────────────

$(document).ready(function () {
  $('#next-btn').on('click', loadPuzzle);

  // Fetch remaining puzzle count
  $.getJSON('/api/stats', function (data) {
    updateRemainingCount(data.remaining_puzzles);
  });

  loadPuzzle();
});

// ── Load a random puzzle ────────────────────────────────

function loadPuzzle() {
  puzzleActive = false;
  clearHighlights();
  setStatus('Loading\u2026', '');
  $('#result-detail').addClass('hidden');

  $.getJSON('/api/puzzle/random')
    .done(function (puzzle) {
      currentPuzzle = puzzle;
      game = new Chess(puzzle.fen);

      var cfg = {
        position:    puzzle.fen,
        orientation: puzzle.player_color,
        draggable:   true,
        pieceTheme:  PIECE_THEME,
        onDragStart: onDragStart,
        onDrop:      onDrop,
        onSnapEnd:   onSnapEnd,
      };

      if (board) {
        board.destroy();
      }
      board = Chessboard('board', cfg);

      populateInfo(puzzle);
      var side = puzzle.player_color === 'white' ? 'White' : 'Black';
      setStatus('Find the best move (' + side + ', move ' + puzzle.move_number + ')', 'solving');
      puzzleActive = true;
    })
    .fail(function () {
      setStatus('Failed to load puzzle', 'incorrect');
    });
}

// ── Board callbacks ─────────────────────────────────────

function onDragStart(source, piece) {
  if (!puzzleActive) return false;

  // Only allow moving the player's pieces
  if (currentPuzzle.player_color === 'white' && piece.search(/^b/) !== -1) return false;
  if (currentPuzzle.player_color === 'black' && piece.search(/^w/) !== -1) return false;

  return true;
}

function onDrop(source, target) {
  if (!puzzleActive) return 'snapback';

  // Attempt the move (auto-queen promotions)
  var move = game.move({
    from: source,
    to: target,
    promotion: 'q',
  });

  if (move === null) return 'snapback';

  // Build UCI string
  var userUci = move.from + move.to;
  if (move.promotion) {
    userUci += move.promotion;
  }

  puzzleActive = false;
  setStatus('Evaluating\u2026', 'solving');

  // Send to backend for Stockfish evaluation
  $.ajax({
    url: '/api/evaluate',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      fen: currentPuzzle.fen,
      user_move_uci: userUci,
      move_id: currentPuzzle.move_id,
    }),
    success: function (res) {
      stats.attempted++;

      if (res.result === 'perfect') {
        stats.correct++;
        setStatus('Perfect! ' + res.best_move_san + ' was the best move.', 'correct');
        highlightSquares(move.from, move.to, 'highlight-correct');

      } else if (res.result === 'pass') {
        stats.correct++;
        setStatus('Good enough! Your move passes the threshold.', 'pass');
        highlightSquares(move.from, move.to, 'highlight-pass');

      } else {
        setStatus('Incorrect \u2014 the best move was ' + res.best_move_san, 'incorrect');
        // Reset board and highlight the correct move
        game = new Chess(currentPuzzle.fen);
        board.position(currentPuzzle.fen, false);
        var bestFrom = res.best_move_uci.substring(0, 2);
        var bestTo   = res.best_move_uci.substring(2, 4);
        highlightSquares(bestFrom, bestTo, 'highlight-correct');
      }

      showResultDetail(res);
      updateStats();

      // Update remaining puzzle count from server
      if (res.remaining_puzzles !== undefined) {
        updateRemainingCount(res.remaining_puzzles);
      }
    },
    error: function () {
      setStatus('Evaluation failed', 'incorrect');
    },
  });
}

function onSnapEnd() {
  board.position(game.fen());
}

// ── UI helpers ──────────────────────────────────────────

function setStatus(text, cls) {
  var $el = $('#status');
  $el.text(text);
  $el.removeClass('solving correct incorrect pass').addClass(cls);
}

function populateInfo(puzzle) {
  $('#info-opponent').text(puzzle.opponent);
  $('#info-date').text(puzzle.date_played || '\u2014');
  $('#info-tc').text(formatTimeControl(puzzle.time_control));
  $('#info-phase').text(capitalise(puzzle.game_phase || '\u2014'));
  $('#info-move').text(puzzle.move_number);

  var evalPawns = (puzzle.eval_before / 100).toFixed(1);
  var sign = puzzle.eval_before >= 0 ? '+' : '';
  $('#info-eval').text(sign + evalPawns);

  if (puzzle.game_url) {
    $('#game-link').attr('href', puzzle.game_url).show();
  } else {
    $('#game-link').hide();
  }
}

function showResultDetail(res) {
  var lines = [];

  // What the user just played
  lines.push(
    'You played <span class="move-san">' + res.user_move_san + '</span>' +
    ' (' + formatCpLoss(res.user_cp_loss) + ')'
  );

  // Best move (if user didn't play it)
  if (res.result !== 'perfect') {
    lines.push(
      'Best move: <span class="move-san">' + res.best_move_san + '</span>'
    );
  }

  // What was played in the actual game
  lines.push(
    'In the game: <span class="move-san">' + res.actual_move_san + '</span>' +
    ' (<span class="cp-loss">' + Math.round(res.actual_cp_loss) + ' cp loss</span>)'
  );

  // Threshold info
  lines.push(
    '<span class="threshold-info">Puzzle threshold: ' + Math.round(res.threshold) + ' cp</span>'
  );

  $('#result-detail').html(lines.join('<br>')).removeClass('hidden');
}

function formatCpLoss(cpLoss) {
  var rounded = Math.round(cpLoss);
  if (rounded === 0) {
    return '<span class="cp-perfect">0 cp loss</span>';
  } else {
    return '<span class="cp-loss">' + rounded + ' cp loss</span>';
  }
}

function updateStats() {
  $('#stat-attempted').text(stats.attempted);
  $('#stat-correct').text(stats.correct);
}

function updateRemainingCount(n) {
  $('#stat-remaining').text(n.toLocaleString());
}

function highlightSquares(from, to, cls) {
  clearHighlights();
  $('#board .square-' + from).addClass(cls);
  $('#board .square-' + to).addClass(cls);
}

function clearHighlights() {
  $('#board .square-55d63').removeClass(
    'highlight-correct highlight-wrong highlight-pass highlight-hint'
  );
}

function formatTimeControl(tc) {
  if (!tc) return '\u2014';
  var parts = tc.split('/');
  var secs = parseInt(parts[parts.length - 1], 10);
  if (isNaN(secs)) return tc;
  var mins = Math.floor(secs / 60);
  var inc  = 0;
  if (tc.indexOf('+') !== -1) {
    var pieces = tc.split('+');
    secs = parseInt(pieces[0], 10);
    inc  = parseInt(pieces[1], 10);
    mins = Math.floor(secs / 60);
  }
  return mins + (inc ? '+' + inc : '+0');
}

function capitalise(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
