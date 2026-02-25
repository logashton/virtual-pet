// Digital Pet Game
class Pet {
    constructor() {
        this.name = 'Fluffy';
        this.hunger = 50;
        this.happiness = 75;
        this.energy = 80;
        this.health = 90;
        this.petEmoji = '🐱';
        this.age = 0;
        this.lastUpdate = Date.now();
        this.loadGame();
    }

    // Save game to localStorage
    saveGame() {
        const gameState = {
            name: this.name,
            hunger: this.hunger,
            happiness: this.happiness,
            energy: this.energy,
            health: this.health,
            petEmoji: this.petEmoji,
            age: this.age,
            lastUpdate: Date.now()
        };
        localStorage.setItem('petGameState', JSON.stringify(gameState));
    }

    // Load game from localStorage
    loadGame() {
        const saved = localStorage.getItem('petGameState');
        if (saved) {
            const gameState = JSON.parse(saved);
            this.name = gameState.name;
            this.hunger = gameState.hunger;
            this.happiness = gameState.happiness;
            this.energy = gameState.energy;
            this.health = gameState.health;
            this.petEmoji = gameState.petEmoji;
            this.age = gameState.age;
            this.lastUpdate = gameState.lastUpdate;
            
            // Apply time-based degradation
            this.updateStats();
        }
    }

    // Update stats based on time passed
    updateStats() {
        const now = Date.now();
        const timePassed = (now - this.lastUpdate) / 1000 / 60; // minutes
        
        // Stats degrade over time
        this.hunger = Math.min(100, this.hunger + timePassed * 0.5);
        this.happiness = Math.max(0, this.happiness - timePassed * 0.2);
        this.energy = Math.max(0, this.energy - timePassed * 0.1);
        
        // Health is affected by hunger and happiness
        if (this.hunger > 80 || this.happiness < 20) {
            this.health = Math.max(0, this.health - timePassed * 0.3);
        } else {
            this.health = Math.min(100, this.health + timePassed * 0.1);
        }
        
        // Increase age
        this.age += Math.floor(timePassed / 60); // hours
        this.lastUpdate = now;
        
        // Clamp all values
        this.clampStats();
    }

    clampStats() {
        this.hunger = Math.max(0, Math.min(100, this.hunger));
        this.happiness = Math.max(0, Math.min(100, this.happiness));
        this.energy = Math.max(0, Math.min(100, this.energy));
        this.health = Math.max(0, Math.min(100, this.health));
    }

    // Pet actions
    feed() {
        if (this.hunger > 10) {
            this.hunger = Math.max(0, this.hunger - 20);
            this.happiness = Math.min(100, this.happiness + 5);
            return 'Nom nom! 😋';
        }
        return 'Not hungry right now!';
    }

    play() {
        if (this.energy > 20) {
            this.energy = Math.max(0, this.energy - 25);
            this.happiness = Math.min(100, this.happiness + 20);
            this.hunger = Math.min(100, this.hunger + 10);
            return 'Wheee! 🎉';
        }
        return 'Too tired to play...';
    }

    sleep() {
        this.energy = Math.min(100, this.energy + 40);
        this.happiness = Math.min(100, this.happiness + 5);
        this.hunger = Math.min(100, this.hunger + 15);
        return 'Zzzzz... 😴';
    }

    pet() {
        this.happiness = Math.min(100, this.happiness + 15);
        return 'Pet loves you! ❤️';
    }

    clean() {
        this.health = Math.min(100, this.health + 20);
        this.happiness = Math.min(100, this.happiness + 10);
        return 'All sparkly clean! ✨';
    }

    treat() {
        this.hunger = Math.max(0, this.hunger - 15);
        this.happiness = Math.min(100, this.happiness + 25);
        return 'Yum yum! 🍫';
    }

    // Get mood based on stats
    getMood() {
        if (this.health < 20) return 'Sick 🤒';
        if (this.hunger > 80) return 'Starving 😫';
        if (this.energy < 20) return 'Exhausted 😩';
        if (this.happiness < 30) return 'Sad 😢';
        if (this.happiness > 80 && this.hunger < 40) return 'Ecstatic 🥰';
        if (this.happiness > 60) return 'Happy 😊';
        return 'Content 😌';
    }
}

// Game UI Controller
class GameUI {
    constructor(pet) {
        this.pet = pet;
        this.initElements();
        this.attachEventListeners();
        this.update();
        
        // Update stats every second
        setInterval(() => this.updateLoop(), 1000);
    }

    initElements() {
        this.elements = {
            petName: document.getElementById('petName'),
            petAge: document.getElementById('petAge'),
            petEmoji: document.getElementById('petEmoji'),
            petMood: document.getElementById('petMood'),
            hunger: document.getElementById('hungerValue'),
            hungerBar: document.getElementById('hungerBar'),
            happiness: document.getElementById('happinessValue'),
            happinessBar: document.getElementById('happinessBar'),
            energy: document.getElementById('energyValue'),
            energyBar: document.getElementById('energyBar'),
            health: document.getElementById('healthValue'),
            healthBar: document.getElementById('healthBar'),
            feedBtn: document.getElementById('feedBtn'),
            playBtn: document.getElementById('playBtn'),
            sleepBtn: document.getElementById('sleepBtn'),
            petBtn: document.getElementById('petBtn'),
            cleanBtn: document.getElementById('cleanBtn'),
            treatBtn: document.getElementById('treatBtn'),
            nameInput: document.getElementById('nameInput'),
            nameBtn: document.getElementById('nameBtn'),
            petSelect: document.getElementById('petSelect'),
            petTypeBtn: document.getElementById('petTypeBtn'),
            resetBtn: document.getElementById('resetBtn'),
            logoutBtn: document.getElementById('logoutBtn')
        };
    }

    attachEventListeners() {
        this.elements.feedBtn.addEventListener('click', () => this.action('feed'));
        this.elements.playBtn.addEventListener('click', () => this.action('play'));
        this.elements.sleepBtn.addEventListener('click', () => this.action('sleep'));
        this.elements.petBtn.addEventListener('click', () => this.action('pet'));
        this.elements.cleanBtn.addEventListener('click', () => this.action('clean'));
        this.elements.treatBtn.addEventListener('click', () => this.action('treat'));
        
        this.elements.nameBtn.addEventListener('click', () => this.setName());
        this.elements.petTypeBtn.addEventListener('click', () => this.changePetType());
        this.elements.resetBtn.addEventListener('click', () => this.resetGame());
        this.elements.logoutBtn.addEventListener('click', (e) => this.logout(e));
        
        this.elements.nameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.setName();
        });
    }

    action(actionName) {
        const message = this.pet[actionName]();
        this.showMessage(message);
        this.pet.clampStats();
        this.pet.saveGame();
        this.update();
    }

    setName() {
        const newName = this.elements.nameInput.value.trim();
        if (newName) {
            this.pet.name = newName;
            this.elements.nameInput.value = '';
            this.pet.saveGame();
            this.update();
        }
    }

    changePetType() {
        this.pet.petEmoji = this.elements.petSelect.value;
        this.pet.saveGame();
        this.update();
    }

    resetGame() {
        if (confirm('Are you sure you want to reset the game? This cannot be undone.')) {
            localStorage.removeItem('petGameState');
            location.reload();
        }
    }

    logout(e) {
        e.preventDefault();
        if (confirm('Are you sure you want to logout? Your game progress will be saved.')) {
            localStorage.removeItem('isLoggedIn');
            window.location.href = 'login.html';
        }
    }

    showMessage(message) {
        // Create temporary message element
        const msg = document.createElement('div');
        msg.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #00695c;
            color: white;
            padding: 20px 40px;
            border-radius: 10px;
            font-size: 18px;
            z-index: 1000;
            animation: fadeInOut 1s ease-in-out;
        `;
        msg.textContent = message;
        document.body.appendChild(msg);
        
        setTimeout(() => msg.remove(), 1000);
    }

    update() {
        // Update UI elements
        this.elements.petName.textContent = this.pet.name;
        this.elements.petAge.textContent = `Age: ${this.pet.age} hours`;
        this.elements.petEmoji.textContent = this.pet.petEmoji;
        this.elements.petMood.textContent = this.pet.getMood();
        
        // Update stat bars
        this.elements.hunger.textContent = Math.round(this.pet.hunger);
        this.elements.hungerBar.style.width = this.pet.hunger + '%';
        
        this.elements.happiness.textContent = Math.round(this.pet.happiness);
        this.elements.happinessBar.style.width = this.pet.happiness + '%';
        
        this.elements.energy.textContent = Math.round(this.pet.energy);
        this.elements.energyBar.style.width = this.pet.energy + '%';
        
        this.elements.health.textContent = Math.round(this.pet.health);
        this.elements.healthBar.style.width = this.pet.health + '%';
    }

    updateLoop() {
        this.pet.updateStats();
        this.pet.saveGame();
        this.update();
    }
}

// Add CSS for animations
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInOut {
        0% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
        50% { opacity: 1; }
        100% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
    }
`;
document.head.appendChild(style);

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Check if user is logged in
    if (!localStorage.getItem('isLoggedIn')) {
        window.location.href = 'login.html';
        return;
    }
    
    const pet = new Pet();
    const ui = new GameUI(pet);
});
