import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';

const canvas = document.getElementById('pet-3d-canvas');
if (!canvas || !window.PET_HAS_3D || !window.PET_MODEL_3D_URL) {
  // Nothing to do.
} else {
  const wrap = document.getElementById('portrait-wrap');
  const placeholder = document.getElementById('portrait-placeholder');
  if (placeholder) placeholder.style.display = 'none';

  canvas.style.display = 'block';

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a24);

  const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 100);
  camera.position.set(2.5, 1.8, 2.5);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const ambient = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(ambient);
  const dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(3, 5, 4);
  scene.add(dir);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.target.set(0, 0.5, 0);

  function addModel(model) {
    if (!model) return;
    model.traverse((o) => {
      if (o.isMesh) {
        o.castShadow = true;
        o.receiveShadow = true;
        if (o.material) o.material.transparent = true;
      }
    });
    const box = new THREE.Box3().setFromObject(model);
    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    const scale = 1.2 / maxDim;
    model.scale.setScalar(scale);
    const center = new THREE.Vector3();
    box.getCenter(center);
    model.position.sub(center.multiplyScalar(scale));
    scene.add(model);
  }

  function onError() {
    if (placeholder) {
      placeholder.style.display = 'flex';
      placeholder.textContent = 'Could not load 3D model';
    }
  }

  const url = window.PET_MODEL_3D_URL;
  const isObj = /\.obj(\?|$)/i.test(url);

  if (isObj) {
    fetch(url)
      .then((r) => r.text())
      .then((text) => {
        const objLoader = new OBJLoader();
        const model = objLoader.parse(text);
        addModel(model);
      })
      .catch(onError);
  } else {
    const gltfLoader = new GLTFLoader();
    gltfLoader.load(
      url,
      (gltf) => {
        const model = gltf.scene || gltf.scenes[0];
        addModel(model);
      },
      undefined,
      onError
    );
  }

  function onResize() {
    if (!wrap) return;
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    if (!w || !h) return;
    canvas.width = w;
    canvas.height = h;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }

  requestAnimationFrame(() => {
    onResize();
    const ro = new ResizeObserver(() => onResize());
    if (wrap) ro.observe(wrap);
  });
  window.addEventListener('resize', onResize);

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();
}
