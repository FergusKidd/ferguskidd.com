title: Generated Textures but with Depth
date: 2023-01-16
slug: generated-textures-but-with-depth
feature_image: /static/images/Dream/Dream Textures.png

<p>One very cool open source project has taken Stable diffusion into Blender. This means you can generate AI art, whether it be concept art, or a texture, right where you need it.</p>

<div class="text-center my-6">
    <a href="https://github.com/carson-katri/dream-textures" class="inline-flex items-center px-6 py-3 bg-steel-blue text-white font-semibold rounded-lg shadow-md hover:bg-blue-700 transition-colors duration-300">
        <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z" clip-rule="evenodd"></path>
        </svg>
        View on GitHub
    </a>
</div>

<p>One epic feature of this project that was just released though is a new model that can deal with the depth it receives from Blender. So not only does it generate something new, it can also understand your model and wrap the texture around it. It seems to do this by asking the model for a mew flat image, knowing what surfaces it meeds to wrap. It makes for a nice addition, but can drastically reduce the quality of the image if you aren't zoomed in on your Blender viewport.</p>

<figure class="kg-card kg-image-card">
    <img src="/static/images/Dream/Cereal.png" class="kg-image" alt="Cereal box texture example" loading="lazy">
</figure>

<p>Here I've asked for a simple texture of a cereal box on a simple mesh. The output is obviously not perfect, generative AI has never yet been great at rendering text nicely, but it's very clearly a cereal box that we have rendered out. </p>

<p>As a distant background object this would be more than enough to quickly fill out a scene, or make interesting new models on the fly. It can use cloud compute if you have a Dream Studio, or locally on your own GPU.</p>

{{azure_video:CerealExample.mp4}}

<p>Here it is in action, going from a blank cuboid to a fully textured cereal box!</p>

<p>Blender is using my Nvidia 3080 to render this nice and quickly locally. The nice addition here is that makes it completely free! </p>
