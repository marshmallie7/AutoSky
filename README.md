# AutoSky ⁠- A 3D skybox automation tool for Source Engine levels

<p align="center">
	<img
		src="https://i.imgur.com/osb0YWY.png"
	/>
</p>
<p align="center">
	<img
		src="https://i.imgur.com/ectYPx0.png"
	/>
</p>

## Features

* Automatically generates 3D skyboxes for any Source Engine level*! Simply do all your skybox detailing in full scale around the main map, add said detailing to a visgroup named exactly “AutoSky” (no quotes), and let AutoSky take care of the rest!
* If configured to its maximum capabilities, AutoSky enables you to do all your skybox design at full scale without ever having to directly modify the 3D skybox yourself; see the in-depth guide for optimal usage [on TF2Maps.net](https://tf2maps.net/threads/resource-guide-streamlining-your-3d-skybox-design-management-workflow-with-autosky.41988).

Configurable options include:

* __Export mode -__ export either the 3D skybox only, or the input VMF with the 3D skybox copied in. With the latter option, the 3D skybox will be cleanly inserted at ~192 units below the lowest point of the input VMF (below the map origin). It will also be placed in its own visgroup labelled “3D Skybox (AutoSky)”, overwriting anything already in that visgroup.

* __Automatically replace models with their skybox counterparts -__ AutoSky comes with an index of every model + skybox variant pair in Team Fortress 2, to which you can add any custom models you’re using and their skybox variants. If this option is enabled, AutoSky will replace any models specified within the index upon moving them to the skybox.

* __Automatically copy fog settings from input VMF’s fog_controller to output skybox’s sky_camera -__ If enabled, AutoSky will make the output skybox’s fog match that of your base map, copying all fog settings from the first env_fog_controller it finds in your input VMF to the sky_camera within the skybox it outputs. (Note that the env_fog_controller does not need to be in the AutoSky visgroup for AutoSky to recognize it.)

*AutoSky has been mainly developed and tested for use with Team Fortress 2, so you may encounter issues with newer VMF formats. Please report any issues you find TF2 or otherwise [here](https://github.com/Sweepertank/AutoSky/issues).

## Download

Latest release: [AutoSky 1.0-beta.1](https://github.com/Sweepertank/AutoSky/releases/tag/v1.0-beta.1)

## Optional Add-ons

* _(For Team Fortress 2 use specifically)_ - the [AutoSky Prop Pack](https://tf2maps.net/threads/autosky-prop-pack.41989/), a collection of 16x and 1/16x scale variants of various stock TF2 models, curated to enhance the convenience of AutoSky's model replacement feature. Every model in the pack is included in the default replacement index. Strongly recommended for TF2 mappers!

## Compatibility

Currently Windows only.

## Contributions

[PyVMF](https://github.com/GorangeNinja/PyVMF) - a VMF parsing library by GorangeNinja
