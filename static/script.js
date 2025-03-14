$(function () {
  // Connexion à Socket.IO en forçant WebSocket pour éviter les erreurs 502 sur certaines plateformes
  var socket = io({
    transports: ["websocket"],
    upgrade: false,
  });

  // Initialiser les animations et les sons
  initAnimations();

  socket.on("connect", function () {
    console.log("✅ Connecté à Pandora Show via Socket.IO");
    showToast("Connecté au serveur !");
  });

  socket.on("teams_updated", function (data) {
    console.log("⚡ teams_updated", data);
    animateScoreChange($("#scoreTeam1"), data.scores[1]);
    animateScoreChange($("#scoreTeam2"), data.scores[2]);
    updatePlayersList(data.players);
  });

  socket.on("roulette_result", function (data) {
    animateThemeChange(data.theme);
  });

  socket.on("countdown_started", function (data) {
    console.log("⏳ Compte à rebours démarré pour " + data.seconds + "s");
    $(".countdownFinished").hide();
    animateCountdownStart(data.seconds);
  });

  socket.on("countdown_tick", function (data) {
    console.log("⏳ Tick reçu:", data.seconds);
    updateCountdown(data.seconds);
  });

  socket.on("countdown_stopped", function () {
    console.log("⏹️ Compte à rebours arrêté");
    resetCountdown();
    showToast("Compte à rebours arrêté !");
  });

  socket.on("countdown_finished", function () {
    console.log("✅ Compte à rebours terminé !");
    finishCountdown();
    playSound("countdown-end");
  });

  socket.on("quiz_question", function (data) {
    animateNewQuestion(data.question);
  });

  socket.on("quiz_answer", function (data) {
    revealAnswer(data.answer);
    playSound("answer-reveal");
  });

  socket.on("dice_result", function (data) {
    animateDiceRoll(data.value);
    playSound("dice-roll");
  });

  socket.on("chat_message", function (data) {
    appendChatMessage(data);
  });

  socket.on("chat_history", function (data) {
    $(".chatMessages").empty();
    data.forEach(function (msg) {
      appendChatMessage(msg);
    });
  });

  // Ciblage des formulaires de chat via leur classe commune
  $(".chatForm").submit(function (e) {
    e.preventDefault();
    var message = $(this).find(".chatInput").val().trim();
    var username = window.username || "Anonyme";
    if (message !== "") {
      socket.emit("chat_message", { user: username, message: message });
      $(this).find(".chatInput").val("");
    }
  });

  function initAnimations() {
    preloadSounds();
    $(".game-card").addClass("animate__animated animate__fadeIn");
  }

  function animateScoreChange(element, newScore) {
    const currentScore = parseInt(element.text());
    if (newScore > currentScore) {
      element.addClass("animate__animated animate__heartBeat");
      element.css("color", "#4caf50");
      setTimeout(function () {
        element.removeClass("animate__animated animate__heartBeat");
        element.css("color", "white");
      }, 1000);
      playSound("score-up");
    } else if (newScore < currentScore) {
      element.addClass("animate__animated animate__shakeX");
      element.css("color", "#f44336");
      setTimeout(function () {
        element.removeClass("animate__animated animate__shakeX");
        element.css("color", "white");
      }, 1000);
      playSound("score-down");
    }
    $({ score: currentScore }).animate(
      { score: newScore },
      {
        duration: 1000,
        easing: "swing",
        step: function () {
          element.text(Math.floor(this.score));
        },
        complete: function () {
          element.text(newScore);
        },
      }
    );
  }

  function updatePlayersList(players) {
    var playersList = $("#playersList");
    playersList.empty();
    var orderedPlayers = [];
    $.each(players, function (pid, info) {
      orderedPlayers.push({
        id: pid,
        username: info.username,
        team: info.team || 0,
      });
    });
    orderedPlayers.sort(function (a, b) {
      if (a.team === b.team) {
        return a.username.localeCompare(b.username);
      }
      return (a.team || 999) - (b.team || 999);
    });
    $.each(orderedPlayers, function (index, player) {
      let teamClass = player.team ? `team-${player.team}` : "team-none";
      let teamLabel = player.team ? `Équipe ${player.team}` : "Non assigné";
      let initials = player.username.charAt(0).toUpperCase();
      let playerCard = $("<div>").addClass(
        "player-card animate__animated animate__fadeIn"
      );
      playerCard.html(`
        <div class="player-avatar">${initials}</div>
        <div class="player-name">${player.username}</div>
        <span class="team-badge ${teamClass}">${teamLabel}</span>
      `);
      playersList.append(playerCard);
    });
  }

  function animateThemeChange(theme) {
    const themeElement = $("#currentTheme");
    themeElement.fadeOut(400, function () {
      $(this).text(theme).fadeIn(400);
      $(this).addClass("animate__animated animate__pulse");
      setTimeout(function () {
        themeElement.removeClass("animate__animated animate__pulse");
      }, 1000);
    });
    playSound("theme-change");
  }

  function animateCountdownStart(seconds) {
    $(".countdownDisplay").text(seconds);
    var circumference = 283;
    $(".countdown-circle circle").css({
      "stroke-dasharray": circumference,
      "stroke-dashoffset": "0",
      stroke: "#ff9800",
    });
    $(".countdown-circle")
      .removeClass("animate__bounceIn")
      .addClass("animate__fadeIn");
    setTimeout(function () {
      $(".countdown-circle").removeClass("animate__fadeIn");
    }, 1000);
    playSound("countdown-start");
  }

  function updateCountdown(seconds) {
    if (seconds < 0) return;
    $(".countdownDisplay").text(seconds);
    var circumference = 283;
    var percentage = seconds / 30;
    var offset = circumference - percentage * circumference;
    $(".countdown-circle circle").css("stroke-dashoffset", offset);
    if (seconds <= 5) {
      $(".countdown-circle circle").css("stroke", "#f44336");
      $(".countdownDisplay").addClass("animate__animated animate__heartBeat");
      playSound("tick");
    } else if (seconds <= 10) {
      $(".countdown-circle circle").css("stroke", "#ff9800");
      $(".countdownDisplay").removeClass(
        "animate__animated animate__heartBeat"
      );
    }
  }

  function resetCountdown() {
    $(".countdownDisplay").text("--");
    $(".countdownFinished").hide();
    $(".countdown-circle circle").css({
      stroke: "#ff9800",
      "stroke-dashoffset": "0",
    });
    $(".countdownDisplay").removeClass("animate__animated animate__heartBeat");
  }

  function finishCountdown() {
    $(".countdownDisplay").text("0");
    $(".countdownFinished").show();
    $(".countdown-circle circle").css({
      stroke: "#f44336",
      "stroke-dashoffset": "283",
    });
    $(".countdownFinished").addClass("animate__animated animate__flash");
    setTimeout(function () {
      $(".countdownFinished").removeClass("animate__animated animate__flash");
    }, 2000);
  }

  function animateNewQuestion(question) {
    const questionElement = $(".quizQuestionDisplay");
    $(".quizAnswerContainer").hide();
    questionElement.addClass("animate__animated animate__fadeOut");
    setTimeout(function () {
      questionElement.text(question);
      questionElement.removeClass("animate__animated animate__fadeOut");
      questionElement.addClass("animate__animated animate__fadeIn");
      setTimeout(function () {
        questionElement.removeClass("animate__animated animate__fadeIn");
      }, 500);
    }, 500);
    playSound("new-question");
  }

  function revealAnswer(answer) {
    $(".quizAnswerDisplay").text(answer);
    $(".quizAnswerContainer").hide().fadeIn(800);
    $(".quizAnswerDisplay").addClass("animate__animated animate__bounceIn");
    setTimeout(function () {
      $(".quizAnswerDisplay").removeClass(
        "animate__animated animate__bounceIn"
      );
    }, 1000);
  }

  function animateDiceRoll(value) {
    const diceElements = $(".diceValue");
    diceElements.addClass("roll-animation");
    let rollCount = 0;
    const maxRolls = 10;
    const rollInterval = setInterval(function () {
      if (rollCount < maxRolls) {
        diceElements.text(Math.floor(Math.random() * 6) + 1);
        rollCount++;
      } else {
        clearInterval(rollInterval);
        diceElements.removeClass("roll-animation");
        diceElements.addClass("animate__animated animate__bounceIn");
        diceElements.text(value);
        setTimeout(function () {
          diceElements.removeClass("animate__animated animate__bounceIn");
        }, 1000);
      }
    }, 100);
  }

  function preloadSounds() {
    const sounds = [
      "countdown-start",
      "countdown-end",
      "tick",
      "score-up",
      "score-down",
      "theme-change",
      "new-question",
      "answer-reveal",
      "dice-roll",
    ];
    // Implémentation future pour précharger les fichiers audio
  }

  function playSound(soundId) {
    console.log("Playing sound: " + soundId);
    // Exemple : $("#sound-" + soundId)[0].play();
  }

  function showToast(message) {
    if ($(".toast-container").length === 0) {
      $("body").append(`
        <div class="toast-container" style="position: fixed; bottom: 20px; right: 20px; z-index: 1000;"></div>
      `);
    }
    const toastId = "toast-" + Date.now();
    const toast = $(`
      <div id="${toastId}" class="animate__animated animate__fadeInUp" 
           style="background: #333; color: white; padding: 10px 20px; border-radius: 5px; margin-top: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.3);">
        ${message}
      </div>
    `);
    $(".toast-container").append(toast);
    setTimeout(function () {
      toast.removeClass("animate__fadeInUp").addClass("animate__fadeOutDown");
      setTimeout(function () {
        toast.remove();
      }, 1000);
    }, 3000);
  }

  function appendChatMessage(msg) {
    var chatContainers = $(".chatMessages");
    chatContainers.each(function () {
      var newMessage = $("<div>").text(msg.user + ": " + msg.message);
      if (msg.correct) {
        newMessage.css("color", "green");
      }
      $(this).append(newMessage);
      $(this).scrollTop($(this)[0].scrollHeight);
    });
  }
});
