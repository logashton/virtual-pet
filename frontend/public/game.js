// Digital Pet Game
class Pet {
    constructor() {
        this.name = "Fluffy";
        this.hunger = 50;
        this.happiness = 75;
        this.energy = 80;
        this.health = 90;
        this.petEmoji = "🐱";
        this.lastUpdate = Date.now();
        this.loadGame();
    }

    saveGame() {
        const gameState = {
            name: this.name,
            hunger: this.hunger,
            happiness: this.happiness,
            energy: this.energy,
            health: this.health,
            petEmoji: this.petEmoji,
            lastUpdate: Date.now()
        };

        localStorage.setItem("petGameState", JSON.stringify(gameState));
    }

    loadGame() {
        const saved = localStorage.getItem("petGameState");

        if (saved) {
            const gameState = JSON.parse(saved);
            this.name = gameState.name ?? "Fluffy";
            this.hunger = gameState.hunger ?? 50;
            this.happiness = gameState.happiness ?? 75;
            this.energy = gameState.energy ?? 80;
            this.health = gameState.health ?? 90;
            this.petEmoji = gameState.petEmoji ?? "🐱";
            this.lastUpdate = gameState.lastUpdate ?? Date.now();

            this.updateStatsOverTime();
        }
    }

    updateStatsOverTime() {
        const now = Date.now();
        const minutesPassed = (now - this.lastUpdate) / 1000 / 60;

        this.hunger += minutesPassed * 0.5;
        this.happiness -= minutesPassed * 0.2;
        this.energy -= minutesPassed * 0.15;

        if (this.hunger > 80 || this.happiness < 20) {
            this.health -= minutesPassed * 0.25;
        } else {
            this.health += minutesPassed * 0.05;
        }

        this.lastUpdate = now;
        this.clampStats();
    }

    clampStats() {
        this.hunger = Math.max(0, Math.min(100, this.hunger));
        this.happiness = Math.max(0, Math.min(100, this.happiness));
        this.energy = Math.max(0, Math.min(100, this.energy));
        this.health = Math.max(0, Math.min(100, this.health));
    }

    feed() {
        if (this.hunger <= 10) {
            return "Your pet isn't hungry right now.";
        }

        this.hunger -= 20;
        this.happiness += 5;
        this.health += 2;
        this.clampStats();
        return "Nom nom! 😋";
    }

    play() {
        if (this.energy < 20) {
            return "Too tired to play... 😴";
        }

        this.happiness += 20;
        this.energy -= 25;
        this.hunger += 10;
        this.clampStats();
        return "Wheee! 🎉";
    }

    sleep() {
        this.energy += 35;
        this.hunger += 10;
        this.clampStats();
        return "Zzzzz... 😴";
    }

    pet() {
        this.happiness += 12;
        this.clampStats();
        return "Your pet feels loved! ❤️";
    }

    clean() {
        this.health += 15;
        this.happiness += 5;
        this.clampStats();
        return "All clean and fresh! ✨";
    }

    treat() {
        this.hunger -= 10;
        this.happiness += 15;
        this.health -= 3;
        this.clampStats();
        return "Yum! A tasty treat! 🍫";
    }

    getMood() {
        if (this.health < 20) return "Sick 🤒";
        if (this.hunger > 80) return "Starving 😫";
        if (this.energy < 20) return "Exhausted 😩";
        if (this.happiness < 30) return "Sad 😢";
        if (this.happiness > 80 && this.hunger < 40) return "Ecstatic 🥰";
        if (this.happiness > 60) return "Happy 😊";
        return "Content 😌";
    }
}

class GameUI {
    constructor(pet) {
        this.pet = pet;
        this.initElements();
        this.attachEventListeners();
        this.update();

        setInterval(() => {
            this.pet.updateStatsOverTime();
            this.pet.saveGame();
            this.update();
        }, 5000);
    }

    initElements() {
        this.elements = {
            petName: document.getElementById("petName"),
            petEmoji: document.getElementById("petEmoji"),
            petMood: document.getElementById("petMood"),

            hungerValue: document.getElementById("hungerValue"),
            happinessValue: document.getElementById("happinessValue"),
            energyValue: document.getElementById("energyValue"),
            healthValue: document.getElementById("healthValue"),

            hungerBar: document.getElementById("hungerBar"),
            happinessBar: document.getElementById("happinessBar"),
            energyBar: document.getElementById("energyBar"),
            healthBar: document.getElementById("healthBar"),

            feedBtn: document.getElementById("feedBtn"),
            playBtn: document.getElementById("playBtn"),
            sleepBtn: document.getElementById("sleepBtn"),
            petBtn: document.getElementById("petBtn"),
            cleanBtn: document.getElementById("cleanBtn"),
            treatBtn: document.getElementById("treatBtn"),
            resetBtn: document.getElementById("resetBtn")
        };
    }

    attachEventListeners() {
        this.elements.feedBtn?.addEventListener("click", () => this.handleAction("feed"));
        this.elements.playBtn?.addEventListener("click", () => this.handleAction("play"));
        this.elements.sleepBtn?.addEventListener("click", () => this.handleAction("sleep"));
        this.elements.petBtn?.addEventListener("click", () => this.handleAction("pet"));
        this.elements.cleanBtn?.addEventListener("click", () => this.handleAction("clean"));
        this.elements.treatBtn?.addEventListener("click", () => this.handleAction("treat"));

        this.elements.resetBtn?.addEventListener("click", (e) => {
            e.preventDefault();
            this.resetGame();
        });
        this.elements.logoutBtn?.addEventListener("click", (e) => {
            e.preventDefault();
            this.logout();
        });
    }

    handleAction(actionName) {
        const message = this.pet[actionName]();
        this.pet.saveGame();
        this.update();
        this.showMessage(message);
    }

    resetGame() {
        const confirmed = confirm("Are you sure you want to reset the game?");
        if (!confirmed) return;

        localStorage.removeItem("petGameState");
        this.pet = new Pet();
        this.update();
        this.showMessage("Game reset! 🔄");
    }

    logout() {
        const confirmLogout = confirm("Are you sure you want to log out?");
        if (!confirmLogout) return;

        // Clear login state
        localStorage.removeItem("isLoggedIn");

        // Redirect to login page
        window.location.href = "login.html";
    }

    showMessage(message) {
        const msg = document.createElement("div");
        msg.textContent = message;
        msg.style.position = "fixed";
        msg.style.top = "30px";
        msg.style.right = "30px";
        msg.style.padding = "14px 20px";
        msg.style.background = "#00695c";
        msg.style.color = "white";
        msg.style.borderRadius = "10px";
        msg.style.boxShadow = "0 4px 12px rgba(0,0,0,0.2)";
        msg.style.zIndex = "9999";
        msg.style.fontWeight = "bold";

        document.body.appendChild(msg);

        setTimeout(() => {
            msg.remove();
        }, 1500);
    }

    update() {
        if (this.elements.petName) {
            this.elements.petName.textContent = this.pet.name;
        }

        if (this.elements.petEmoji) {
            this.elements.petEmoji.textContent = this.pet.petEmoji;
        }

        if (this.elements.petMood) {
            this.elements.petMood.textContent = this.pet.getMood();
        }

        if (this.elements.hungerValue) {
            this.elements.hungerValue.textContent = Math.round(this.pet.hunger);
        }

        if (this.elements.happinessValue) {
            this.elements.happinessValue.textContent = Math.round(this.pet.happiness);
        }

        if (this.elements.energyValue) {
            this.elements.energyValue.textContent = Math.round(this.pet.energy);
        }

        if (this.elements.healthValue) {
            this.elements.healthValue.textContent = Math.round(this.pet.health);
        }

        if (this.elements.hungerBar) {
            this.elements.hungerBar.style.width = `${this.pet.hunger}%`;
        }

        if (this.elements.happinessBar) {
            this.elements.happinessBar.style.width = `${this.pet.happiness}%`;
        }

        if (this.elements.energyBar) {
            this.elements.energyBar.style.width = `${this.pet.energy}%`;
        }

        if (this.elements.healthBar) {
            this.elements.healthBar.style.width = `${this.pet.health}%`;
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const pet = new Pet();
    new GameUI(pet);
});
